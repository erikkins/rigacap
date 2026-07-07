-- SqlProcedure: [dbo].[watchBuyAboveMaxPricePostLossRetroDate]

--look through all stock transactions that sold for a loss and 
--pull all that don't already have a newer buy
--if their last price exceeds the highest price attained during its 
--previous holding period, buy again!



declare @buydate datetime
declare @selldate datetime
declare @msg varchar(500)
declare @lastprice money
declare @alltime money
declare @lastdatadate datetime
declare @now datetime
select @now = getdate()
declare @buycomment varchar(500)
declare @audit varchar(8000)
declare @ticker varchar(10)
declare @watchID int, @stockID int
declare @channel char(1)
declare @BuyID2 int
declare @retval int
declare @dwapdate datetime
declare @buyDateDWAP money
select @watchID = watchID 
from Watch 
where ProcName = 'watchBuyAboveMaxPricePostLossRetroDate'

exec addWatchHistory @watchID, @RunDate

select @buydate = atwhen,
@stockID=stockID,
@channel=channel,
@dwapdate = dwapdate
from stockbuy
where buyID=@BuyID

select @buyDateDWAP = dbo.fnDWAP(@stockID, @RunDate)

select @selldate = atwhen
from stocksell
where buyID=@buyID

select @lastprice = price
from stockdata
where stockID=@stockID
and atwhen = @RunDate

select @ticker = ticker
from stock
where stockID = @stockID


if @lastprice is null
	begin
		return 0
	end


--Determine if we already have an open buy newer than the loss date...if so, bail
--if exists (select * from stockbuy where stockid=@stockid and status=0 and atwhen > @selldate and dwapdate=@dwapdate)
if exists (select * from stockbuy where stockid=@stockid and status=0 and dwapdate=@dwapdate and channel=@channel)
	begin
		Print 'Denied Rebuy'
		return 0
	end
else
	begin

		--if the lastprice is below the 200DMA, then bail
		declare @200DMAP money
		select @200DMAP = dbo.fn200DMA(@stockID, @RunDate)
		if @lastprice < @200DMAP
			begin		
				--Print 'Denied Rebuy--price under200'		
				return 0
			end

		select @alltime = max(price)
		from stockdata
		where stockid = @stockID
		and atwhen between @buydate and dateadd(day,1,@selldate)

		if @lastprice is not null and @alltime is not null
			begin
				if @lastprice > @alltime and @lastPrice > @buyDateDWAP
					begin
						
						--add the new buy!
						select @audit = 'Buying ' + @ticker + ' on a new high after sell from buyid: ' + convert(varchar,@buyID)
						Print @audit
						exec saveAudit @now,  @audit, @stockID, 'BUYABOVEMAXPRICEPOSTLOSS', 'I'

						declare @strLastPrice varchar(100)
						select @strLastPrice = convert(varchar,@lastprice)
						if @strLastPrice is null
							begin
								select @strLastPrice = '[unknown]'
							end
						declare @strAllTime varchar(100)
						select @strAllTime = convert(varchar,@alltime)
						if @strAllTime is null
							begin
								select @strAllTime = '[unknown]'
							end

							select @buycomment = 'Yesterday''s price of ' + @strLastPrice + ' exceeds the alltime transaction high price of ' + @strAllTime + ' '											
							exec @buyID2 = addBuyChannel @stockID, @watchID, @RunDate, @buycomment, @buyID, 100, @channel, null, 1

							select @retval=0							
							exec @retval = runWatchesSell @BuyID2
							/*
							--but we really should run through the dates and see if this thing would sell otherwise
							declare @yesterday datetime	
							declare @tempdate datetime						
							select @yesterday = dateadd(day,-1,@RunDate)							
							select @lastDataDate = LastDataDate
							from stock
							where stockID=@StockID

							--if @RunDate < @yesterday
								begin
									--call the retro sells													
									if @buyID2 is not null and @BuyID2 != 0
										begin																			
											select @tempdate = @RunDate																					
											select @retval=0										
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
											select @audit='Could not find BuyID for stock in Rebuy F section'
											Print @audit
											select @now = getdate()
											exec saveAudit @now, @audit, @stockID
										end
								end		
							*/								
						return 1
					end
				else
					begin
						--Print 'Denied Rebuy -- Lastprice not high enough'		
						return 0
					end
			end
		else
			begin		
				--Print 'Denied Rebuy -- Lastprice or all time is null'
				return 0
			end
	end
