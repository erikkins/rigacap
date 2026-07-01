-- SqlProcedure: [dbo].[CheckwatchSellKeyTrendReversalRetroDate]

set nocount on

declare @stockID int, @shares decimal(8,3)
declare @lastPrice money, @lastDataDate datetime
declare @yesterdayClose money, @yesterdayHigh money, @yesterdayLow money, @todayHigh money, @todayLow money
declare @52WeekHigh money
declare @BuyDate datetime
declare @200DMAP money

select @StockID = stockID,
@shares = shares,
@BuyDate = atwhen
from StockBuy 
where BuyID=@BuyID

Print 'Checking KeyTrend'
	
declare @rundate datetime

declare buycur cursor for
	select atwhen from stockdata where stockID = @stockID and atwhen > @buydate

open buycur
fetch next from buycur into @rundate
while @@fetch_status=0
	begin			
			select @lastPrice = Price, 
			@todayHigh = DayHigh, 
			@todayLow = DayLow		
			from StockData sd 
			where sd.AtWhen=@RunDate
			and sd.StockID = @StockID

			select @52WeekHigh = max(Price)
			from StockData 
			where stockID=@StockID
			and atwhen between dateadd(day,-365,@RunDate) and @RunDate

			select @yesterdayClose = Price,
			@yesterdayHigh = DayHigh,
			@yesterdayLow = DayLow
			from StockData
			where StockID = @StockID
			and Atwhen = (select max(Atwhen) from stockData where stockID=@stockID and Atwhen < @RunDate)

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
							
							select @200DMAP = dbo.fn200DMA(@stockID, @RunDate)

							if @lastPrice >= @200DMAP * 1.5
								begin
									Print 'Key Trend Reversal occurred on ' + Convert(varchar, @RunDate, 101)
									--exec saveAudit @LastDataDate, 'Key Trend Reversal', @stockID, 'KEYTRENDREVERSAL'
									--exec addSell @buyID, @watchID, @LastDataDate, @shares, 'Key Trend Reversal'
								end
						end
				end		

	fetch next from buycur into @rundate
	end
close buycur
deallocate buycur

Print 'Done checking'
