-- SqlProcedure: [dbo].[watchBuyAboveNewDWAP]

declare @watchID int

select @watchID = watchID 
from Watch 
where ProcName = 'watchBuyAboveNewDWAP'

if @channel is null
	begin
		select @channel ='H'
	end

declare @sid int, @atwhen datetime
declare @xprice money
declare @xvol bigint

declare @buyprice money, @buyDate datetime, @buyVol bigint
declare @ticker varchar(10)
declare @buyID int
declare @yesterday datetime
declare @audit varchar(1000)
select @yesterday = dateadd(day,-1,getdate())
declare @lastDataDate datetime
declare @tempdate datetime, @now datetime
declare @retval int

declare @BuyDateDWAP money, @BuyDate50 money
declare @DWAPDWAP money, @DWAP50 money
declare @slope50 float
declare @daysUnder int

select @now = getdate()
exec addWatchHistory @watchID, @now


declare si2 cursor for
	--select stockID, atwhen from newdwap where active=1 order by atwhen asc
	select nd.stockID, nd.atwhen 
	from newdwap nd
	inner join stockData sd on sd.stockID=nd.stockID and sd.atwhen = nd.atwhen	
	where sd.volume >= 1000000
	and dbo.fnSlope50(nd.stockID, dateadd(day,-30,nd.atwhen), nd.atwhen) > 0
	and dbo.fnSlope(nd.stockID, dateadd(day,-30,nd.atwhen), nd.atwhen) > 0
	and dbo.fnSlope(nd.stockID, dateadd(day,-30,nd.atwhen), nd.atwhen) > dbo.fnSlope50(nd.stockID, dateadd(day,-30,nd.atwhen), nd.atwhen)

open si2
fetch next from si2 into @sid, @atwhen
	while @@fetch_status=0
		begin
		--get the price on this date and then see if it ever goes up 2%
		select @xprice = price, @xvol = volume
		from stockdata
		where stockID=@sid
		and atwhen=@atwhen
		

		--just buy right away on DWAP date
			
																							
		declare @firstBuyPrice money		
		select @firstBuyPrice = @xprice
																								
		if exists (select * from stockdata where stockID=@sid and atwhen >= @atwhen )
			begin
				select @buyDate = @atwhen
				/*																							
				select top 1 @buyprice = price, @buyDate=atwhen, @buyVol = volume 
				from stockdata sd
				where stockID=@sid 
				and atwhen > @atwhen
				--and price >=@firstBuyPrice 
				--and price >= dbo.fnDWAP(@sid,atwhen)
				order by atwhen asc					
	
				select @BuyDateDwap = dbo.fnDWAP(@sid, @buydate)

				select @slope50 = dbo.fnSlope50(@sid, @atwhen, @buydate)
				--select @DWAPDWAP = dbo.fnDWAP(@sid, @atwhen)
				--select @DWAP50 = dbo.fn50DMA(@sid, @atwhen)
				--select @buyDate50 = dbo.fn50DMA(@sid, @buyDate)
				
				select @daysUnder = count(*) from stockdata
				where atwhen between @atwhen and @buyDate
				and price < dbo.fnDWAP(stockID,atwhen) and price < dbo.fn50DMA(stockID,atwhen)
				and stockID=@sid

				*/

				--before there was also a @buyprice > 25 requirement		
						--if @buyprice > (@buyDateDwap * 1.01) and @Slope50 > 0 and @daysUnder = 0 --and dbo.PeriodBeforeSlope(@sid,@atwhen,@buydate) > .7 --and @DWAPDWAP > @DWAP50 and @BuyDateDwap > @BuyDate50 --and @DWAPDWAP > @DWAP50							
							BegiN
									select @ticker = ticker, @lastDataDate=lastdatadate from stock where stockID=@sid										

									select @audit = @ticker + ' exceeded 2% DWAP price cross'
									exec saveAudit @buyDate,  @audit, @sid, '2%ABOVEDWAP','I'

									declare @comment varchar(1000)
									select @comment =  'Price exceeded 2% above DWAP price cross'											
									exec @buyID = addbuyChannel @sid, @watchID, @buydate,@comment, null, 100, @channel, @atwhen, 1	

									if @buydate < @yesterday
									begin
										--call the retro sells													
										if @buyID is not null and @BuyID != 0
											begin															
												exec @retval = runWatchesSell @BuyID												
											end														
										else
											begin
												if @buyID is null
													begin																
														select @audit='Could not find BuyID for stock in watchBuyAboveNewDWAP H section'
														Print @audit
													end
												else
													begin
														select @audit='Stock already held during this period in watchBuyAboveNewDWAP H section'												
													end										
												
												exec saveAudit @now, @audit, @sid
											end
									end
							EnD		
			end

		fetch next from si2 into @sid, @atwhen
		end
close si2
deallocate si2
Print 'DONE'
