-- SqlProcedure: [dbo].[watchBuy10AboveDWAPTouchback]

declare @watchID int

select @watchID = watchID 
from Watch 
where ProcName = 'watchBuy10AboveDWAPTouchback'

if @channel is null
	begin
		select @channel ='G'
	end

declare @sid int, @atwhen datetime
declare @xprice money
declare @xvol bigint
declare @buyprice money, @buyDate datetime, @buyVol bigint
declare @200DMAP money
declare @50DMAP money
declare @50DMAPX money --the 50DMAP when DWAP was crossed
declare @avg bigint
declare @ticker varchar(10)
declare @DWAP2BUY money, @DWAPPeriodGain decimal(5,1)
declare @DWAPAvgToDWAP decimal(5,1)
declare @cnt int
select @cnt = 0
declare @buyID int
declare @yesterday datetime
declare @audit varchar(1000)
select @yesterday = dateadd(day,-1,getdate())
declare @lastDataDate datetime
declare @tempdate datetime, @now datetime
declare @retval int
declare @touchback datetime
declare @buyDateDWAP money
declare @DWAPDWAP money

declare @PeriodUnder bit
select @PeriodUnder = 0
declare @currentunder datetime
declare @curr50 money, @curr200 money, @currprice money
declare @goodCurve bit

select @now = getdate()
exec addWatchHistory @watchID, @now


declare si2 cursor for
	--select stockID, atwhen from newdwap where active=1 order by atwhen asc
	
	select nd.stockID, nd.atwhen from newdwap nd
	inner join stockdata sd on sd.stockID=nd.stockID and sd.atwhen=nd.atwhen
	where active=1 
	and sd.Price > 25	--was 50
	order by atwhen asc
	
open si2
fetch next from si2 into @sid, @atwhen
	while @@fetch_status=0
		begin
		--get the price on this date and then see if it ever goes up 10%
		select @xprice = price, @xvol = volume
		from stockdata
		where stockID=@sid
		and atwhen=@atwhen

		--first time it touches back to the line after reaching 5%
		declare @dateRise datetime
		declare @risePrice money

		select @dateRise = min(atwhen)
		from stockData
		where stockID=@sid
		and price > @xprice * 1.05
		and atwhen > @atwhen

		select @touchback = min(atwhen)
		from stockData
		where stockID=@sid
		and atwhen > @daterise
		and price <= @xprice

		select @risePrice = max(price)
		from stockdata
		where stockID = @sid
		and atwhen between @atwhen and @touchback
																							
		declare @firstBuyPrice money
		--make the first buyprice be 1/2 way between the DWAP cross and the peak risePrice
		select @firstBuyPrice = (@xprice + @risePrice)/2
																								--was @xprice, then was @riseprice
		if exists (select * from stockdata where stockID=@sid and atwhen > @touchback and price >= @firstBuyPrice )--and volume > 1000000)
			begin											
				
				
				--select top 1 @buyprice = price, @buyDate=atwhen, @buyVol = volume from stockdata where stockID=@sid and atwhen > @touchback and price >=@xprice and volume > 1000000 order by atwhen asc																									--vol was 1500000
				select top 1 @buyprice = price, @buyDate=atwhen, @buyVol = volume from stockdata where stockID=@sid and atwhen > @touchback and price >=@risePrice order by atwhen asc
				select @200DMAP = dbo.fn200DMA(@sid, @buyDate)
				select @50DMAP = dbo.fn50DMA(@sid, @buyDate)
				select @50DMAPX = dbo.fn50DMA(@sid, @atwhen)
				select @avg = avg(volume) from stockdata where stockID=@sid and atwhen between @atwhen and @buydate
				select @buyDateDWAP = dbo.fnDWAP(@sid, @buyDate)
				select @DWAPDWAP = dbo.fnDWAP(@sid, @atwhen)
				select @goodCurve=1
				
				--one of the conditions isn't true...which?  if it swoops down below, then don't buy!
				--if @50DMAPX > @DWAPDWAP and @50DMAP < @BuyDateDWAP
				--	begin
				--		select @goodCurve=0
				--	end				
	
				--before there was also a @buyprice > 25 requirement
				if @buyprice > @200DMAP and @avg > 1000000 and @buyprice > @buyDateDWAP * 1.02 and @goodCurve=1   -- and @buyVol > @xvol and @xprice > @50DMAPX														
						BEGIN				
							--now check each day between the DWAP and the proposed Buy Date.  If the price ever went under BOTH 50 and 200 DMAs, then don't buy
							select @PeriodUnder = 0
							select @currentunder = @atwhen
							while @currentunder < @buydate
								begin
									select @currprice = price from stockData where stockID=@sid and atwhen=@currentunder
									select @curr50 = dbo.fn50DMA(@sid,@currentunder)
									select @curr200 = dbo.fn200DMA(@sid, @currentunder)
									if @currprice < @curr50 and @currprice < @curr200
										begin
											select @PeriodUnder=1
											select @currentunder = @buydate
											--Print 'Price fell under both 50 and 200 DMAs.  Do not buy. ' + Convert(varchar,@sid) + '--' + Convert(varchar,@currentunder,101) + ' for buydate ' + convert(varchar,@buydate,101)
											break
										end
									select @currentunder = dateadd(day,1,@currentunder)
								end				
							if @PeriodUnder=0		
							BegiN

									select @ticker = ticker, @lastDataDate=lastdatadate from stock where stockID=@sid										

									select @audit = @ticker + ' exceeded 10% DWAP price cross at > 1M volume sustainable'
									exec saveAudit @buyDate,  @audit, @sid, '10%ABOVEDWAPSUSTAIN','I'

									declare @comment varchar(1000)
									select @comment =  'Price exceeded 10% above DWAP Price Cross at > 1M volume sustainable'											
									exec @buyID = addbuyChannel @sid, @watchID, @buydate,@comment, null, 100, @channel, @atwhen, 1	

									if @buydate < @yesterday
									begin
										--call the retro sells													
										if @buyID is not null and @BuyID != 0
											begin			
												/*																
												select @tempdate = @buydate																					
												select @retval=0										
												while (@tempdate < @lastDataDate) AND @retval=0
													begin								
														if exists (select * from stocksplit where stockID=@sid and atwhen=@tempdate and applydate is null)
															begin
																exec applySplit @sid, @tempdate
															end					
														
														exec @retval = runWatchesRetroDate @buyID, @tempdate
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
												*/
												exec @retval = runWatchesSell @BuyID
												/*
												if @retval=0
													begin
														Print 'Still holding BuyID:' + Convert(varchar, @BuyID)
													end																												
												*/
											end														
										else
											begin
												if @buyID is null
													begin																
														select @audit='Could not find BuyID for stock in watchBuy10AboveDWAPCross F section'
														Print @audit
													end
												else
													begin
														select @audit='Stock already held during this period in watchBuy10AboveDWAPCross F section'												
													end																						
												exec saveAudit @now, @audit, @sid
											end
									end
							EnD
						END					
			end

		fetch next from si2 into @sid, @atwhen
		end
close si2
deallocate si2
Print 'DONE'
