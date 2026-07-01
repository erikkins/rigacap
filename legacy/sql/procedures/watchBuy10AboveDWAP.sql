-- SqlProcedure: [dbo].[watchBuy10AboveDWAP]

--this is a buy watch, but we're not using the startdate ever...

declare @stockID int, @dwapdate datetime

declare @watchID int
declare @ticker varchar(5)

declare @buyID int, @BuyID2 int

declare @now datetime
select @now = getdate()
declare @audit varchar(8000)

select @watchID = watchID 
from Watch 
where ProcName = 'watchBuy10AboveDWAP'

exec addWatchHistory @watchID, @now

declare @dwapprice money, @currprice money, @avg float, @buydate datetime, @lastDataDate datetime
declare @DWAP2BUY money, @DWAPPeriodGain decimal(5,1)
declare @DWAPAvgToDWAP decimal(5,1)
declare @yesterday datetime
select @yesterday = dateadd(day,-1,getdate())
declare @tempdate datetime
declare @retval int

if @channel is null
	begin
		select @channel ='D'
	end

declare b10cur cursor for
	select si.stockID, si.atwhen from StockInteresting si inner join stock s on s.stockID=si.stockID where s.Active=1
	open b10cur
	fetch next from b10cur into @stockID, @dwapdate
	while @@fetch_status=0
		begin
			--don't buy if already bought
			if not exists (select * from stockbuy where stockID = @stockID and Status=0 and Channel =@channel)
				begin							
					--select @newhighdate = convert(char(4),datepart(year, atwhen)) + '-' + right('00' + convert(varchar(2),datepart(month, atwhen)),2) + '-'+ right('00' + convert(varchar(2), datepart(day, atwhen)),2)
					select @dwapprice = price
					from stockData
					where StockID = @StockID
					and AtWhen = @dwapdate
					and price >= 22.5
					--and price > 46 --don't need price and volume info on the DWAP cross
					--and Volume > 1000000

					if @dwapprice is null
						begin
							continue
						end

					select @currprice = LastPrice, @avg = LastVolume, @lastDataDate = LastDataDate, @ticker = ticker 
					from Stock
					where StockID = @StockID

					
					--if there was a split after the dwapdate and it was applied, we need to account for that
					declare @revsplitmult decimal(3,2), @splitdate datetime
					select @revsplitmult= 1.0
					declare @split varchar(50)					
					declare @left int, @right int, @colloc int

					if exists (select * from stocksplit where stockID=@stockID and atwhen > @dwapdate and applydate is not null)
					begin
						select @splitdate = atwhen, @split=split from stocksplit where stockID=@stockID and atwhen > @dwapdate and applydate is not null
						select @colloc = charindex(':', @split)
						select @left = substring(@split, 1, @colloc -1), @right = substring(@split, @colloc+1, len(@split)-@colloc+1)
						--note that this is reverse from the apply split, since we are UNAPPLYING the split here
						select @revsplitmult = convert(decimal,@left)/@right												
					end

					select top 1 @buydate = atwhen
					from StockData
					where stockID = @stockID
					and atwhen > @dwapdate
					and Price * @revsplitmult > @dwapprice * 1.10
					and Price * @revsplitmult > 25 --50
					and Volume > 1000000
					order by atwhen asc

					if @buydate is null
						begin
							Print 'BUYDATE is NULL'
							continue
						end

					if @splitdate is null
						begin
							--trick the logic
							select @splitdate = @buydate
						end


					select @currprice = Price * @revsplitmult
					from StockData where atwhen = @buydate
					and StockID = @stockID										

					select @avg = avg(Volume)
					from StockData 
					where atwhen between @dwapdate and @buydate
					and StockID = @stockID

					
					declare @200DMAP money
					declare @50DMAP money
					/*
					select @200DMAP = avg(price)
					from stockdata 
					where atwhen between dateadd(day,-200,@buydate) and dateadd(day,1,@buydate)
					and StockID = @StockID
					*/
					/*
					select top 200 @200DMAP = avg(price)
					from stockdata
					where atwhen <= @buydate
					and stockID = @StockID
					group by atwhen
					order by atwhen desc
					*/

					select @200DMAP = dbo.fn200DMA(@stockID, @buyDate)

					select @50DMAP = dbo.fn50DMA(@stockID, @buydate)
					/*
					select top 50 @50DMAP = avg(price)
					from stockdata
					where atwhen <= @buydate
					and stockID = @StockID
					group by atwhen
					order by atwhen desc
					*/

					--check if the intended buy price is < avg(price) during the DWAP-->BUY period
					

					--if @currprice > 50 and @currprice > @200DMAP
					if @currprice > 25 and @currprice > @200DMAP
						begin
							if @currprice >= @dwapprice * 1.10
								begin
									if @avg > 1000000
										begin
											select @audit = @ticker + ' exceeded 10% DWAP price at > 1M volume'
											exec saveAudit @now,  @audit, @stockID, '10%ABOVEDWAP','I'

											declare @comment varchar(1000)
											select @comment =  'Price exceeded 10% above DWAP Price at > 1M volume'											
											exec @buyID = addbuyChannel @stockID, @watchID, @buydate,@comment, null, 100, @channel, @dwapdate, 1											

											--START E BUYS
											--check if the intended buy price is < avg(price) during the DWAP-->BUY period
											--if it is, don't buy for E group...otherwise buy!
											select @DWAP2BUY = avg(price)
											from stockdata
											where atwhen between @dwapdate and @buydate
											and stockID = @stockID
											select @DWAPPeriodGain = (convert(decimal(5,1),@DWAP2BUY) * 100/@200DMAP)-100
											
											--also if the 50DMA > 200DMA, then buy
											--should be self-fulfilling prophecies
											
											select @DWAPAvgToDWAP = (convert(decimal(5,1),@DWAP2BUY) * 100 / @dwapprice)-100

											if @DWAPPeriodGain > 0 AND (@50DMAP > @200DMAP) AND (@DWAPAvgToDWAP > 0)
												begin
													select @comment =  'Price exceeded 10% above DWAP Price at > 1M volume above DWAP period average'		
													exec @buyID2 = addbuyChannel @stockID, @watchID, @buydate,@comment, null, 100, 'E', @dwapdate, 1

													--start retro for E buys
															if @buydate < @yesterday
																begin
																	--call the retro sells													
																	if @buyID2 is not null and @BuyID2 != 0
																		begin																			
																			select @tempdate = @buydate																					
																			select @retval=0
																			--Print 'HERE ' + Convert(varchar(10),@buyID)
																			while (@tempdate < @lastDataDate) AND @retval=0
																				begin								
																					if exists (select * from stocksplit where stockID=@stockID and atwhen=@tempdate and applydate is null)
																						begin
																							exec applySplit @stockID, @tempdate
																						end					
																					
																					exec @retval = runWatchesRetroDate @buyID2, @tempdate
																					if @retval = 1
																						begin																			
																							select @tempdate = @lastDataDate	
																							break																																																																																																																										
																						end		
																					else
																						begin															
																							select @tempdate = dateadd(day,1,@tempdate)
																						end
																				end																														
																		end														
																	else
																		begin																
																			select @audit='Could not find BuyID for stock in watchBuy10AboveDWAP E section'
																			Print @audit
																			exec saveAudit @now, @audit, @stockID
																		end
																end
														--end retro for E buys
												end
											--END E BUYS


											--now we need to spin through sell rules to see if this puppy should've already sold!
											if @buydate < @yesterday
												begin
													--call the retro sells													
													if @buyID is not null and @BuyID != 0
														begin															
															select @tempdate = @buydate																	
															select @retval=0
															--Print 'HERE ' + Convert(varchar(10),@buyID)
															while (@tempdate < @lastDataDate) AND @retval=0
																begin																																		
																	--Print Convert(varchar(20),@tempdate) + ' -- ' + Convert(varchar(20),@lastDataDate)
																	
																	if exists (select * from stocksplit where stockID=@stockID and atwhen=@tempdate and applydate is null)
																		begin
																			exec applySplit @stockID, @tempdate
																		end
																	
																	exec @retval = runWatchesRetroDate @buyID, @tempdate
																	if @retval = 1
																		begin
																			--we sold somewhere, so get out	
																			--Print 'SOLD BUYID ' + Convert(varchar(10),@buyid) 																			
																			select @tempdate = @lastDataDate	
																			break																																																																																																																										
																		end		
																	else
																		begin															
																			select @tempdate = dateadd(day,1,@tempdate)
																		end
																end																														
														end														
													else
														begin																
															select @audit='Could not find BuyID for stock in watchBuy10AboveDWAP'
															Print @audit
															exec saveAudit @now, @audit, @stockID
														end
												end
											
											--delete from StockInteresting
											--where StockID = @StockID						
										end
									else
										begin							
											select @audit = @ticker + ' would have been purchased at 10% above DWAP, but volume did not exceed 1M'							
											exec saveAudit @now,  @audit, @stockID
										end
								end
						end
				end
		fetch next from b10cur into @stockID, @dwapdate
		end

	close b10cur
	deallocate b10cur
