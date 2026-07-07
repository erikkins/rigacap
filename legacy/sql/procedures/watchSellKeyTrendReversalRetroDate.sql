-- SqlProcedure: [dbo].[watchSellKeyTrendReversalRetroDate]

set nocount on

declare @watchID int, @stockID int, @shares decimal(8,3)
declare @lastPrice money
declare @yesterdayClose money, @yesterdayHigh money, @yesterdayLow money, @todayHigh money, @todayLow money
declare @yesterdayDate datetime
declare @52WeekHigh money
declare @BuyDate datetime
declare @BuyPrice money
declare @200DMAP money
select @watchID = watchID 
from Watch 
where ProcName = 'watchSellKeyTrendReversalRetroDate'

exec addWatchHistory @watchID, @RunDate

select @StockID = stockID,
@shares = shares,
@BuyDate = atwhen
from StockBuy 
where BuyID=@BuyID

select @BuyPrice = Price
from StockData
where StockID=@StockID
and atwhen=@BuyDate
	
--Print 'Checking KeyTrend'
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
			@yesterdayLow = DayLow,
			@yesterdayDate = atwhen
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
									--lock in at 10%  (was 2%)
									if @lastPrice >= @BuyPrice * 1.1
										begin
											exec saveAudit @RunDate, 'Key Trend Reversal', @stockID, 'KEYTRENDREVERSAL'
											exec addSell @buyID, @watchID, @RunDate, @shares, 'Key Trend Reversal'
											Print 'Selling on Key Trend Reversal'
											return 1
										end							
								end
						end
				end		

			return 0
