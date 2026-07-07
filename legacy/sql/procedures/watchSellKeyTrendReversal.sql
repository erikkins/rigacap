-- SqlProcedure: [dbo].[watchSellKeyTrendReversal]

set nocount on

declare @watchID int, @stockID int, @shares decimal(8,3)
declare @buyID int, @lastPrice money, @lastDataDate datetime
declare @yesterdayClose money, @yesterdayHigh money, @yesterdayLow money, @todayHigh money, @todayLow money
declare @52WeekHigh money
declare @200DMAP money

select @watchID = watchID 
from Watch 
where ProcName = 'watchSellKeyTrendReversal'

declare @now datetime
select @now = getdate()
exec addWatchHistory @watchID, @now

declare ktcur cursor for
	select buyID, stockID, shares from StockBuy sb where sb.status=0

open ktcur
	fetch next from ktcur into @buyID, @stockID, @shares
	while @@fetch_status=0
		begin		
			select @lastPrice = LastPrice, 
			@todayHigh = DayHigh, 
			@todayLow = DayLow, 
			@LastDataDate = LastDataDate,
			@52WeekHigh = [52WeekHigh]
			from Stock s
			inner join StockData sd on sd.StockID = s.StockID and sd.AtWhen=s.LastDataDate
			where s.StockID = @StockID

			select @yesterdayClose = Price,
			@yesterdayHigh = DayHigh,
			@yesterdayLow = DayLow
			from StockData
			where StockID = @StockID
			and Atwhen = (select max(Atwhen) from stockData where stockID=@stockID and Atwhen < @LastDataDate)

			if @yesterdayClose >= @52WeekHigh and @yesterdayClose > @lastPrice
				begin
					--now figure out if the previous trading day's spread was narrower than the last trading day's
					if @todayHigh > @yesterdayHigh and @todayLow < @yesterdayClose
						begin
							--but only sell if the current price is atleast 50% above the 200DMAP
							--get the 200DMAP							
							--select @200DMAP = avg(price)
							--from stockdata 
							--where atwhen between dateadd(day,-200,@lastDataDate) and dateadd(day,1,@lastdataDate)
							--and StockID = @StockID
				
							select @200DMAP = dbo.fn200DMA(@stockID, @lastDataDate)

							if @lastPrice >= @200DMAP --* 1.5
								begin
									exec saveAudit @LastDataDate, 'Key Trend Reversal', @stockID, 'KEYTRENDREVERSAL'
									exec addSell @buyID, @watchID, @LastDataDate, @shares, 'Key Trend Reversal'
									Print 'Selling on Key Trend Reversal'
								end
						end
				end		

		fetch next from ktcur into @buyID, @stockID, @shares
		end
close ktcur
deallocate ktcur
