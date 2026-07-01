-- SqlProcedure: [dbo].[watchSellUnder50DWAPRetroDate]

set nocount on

declare @watchID int, @stockID int
declare @shares decimal(8,3), @lastPrice money
declare @50DMA money, @dwap money
declare @buyPrice money, @buyDate datetime

select @watchID = watchID 
from Watch 
where ProcName = 'watchSellUnder50DWAPRetroDate'

exec addWatchHistory @watchID, @RunDate

select @StockID = stockID,
@shares = shares,
@buyDate = atwhen
from StockBuy 
where BuyID=@BuyID


		select @lastPrice = Price
		from StockData
		where StockID=@StockID
		and atwhen = @RunDate

		select @buyPrice=price
		from stockdata
		where atwhen=@buyDate
		and stockID=@stockID

		select @50DMA = dbo.fn50DMA(@stockID, @RunDate)
		select @dwap = dbo.fnDWAP(@stockID, @RunDate)

		if @lastprice is null or @50DMA is null or @DWAP is null
		begin
			--if @dwapdate is null
			--	begin
			--		Print 'LastPrice is null in 8% down'
			--	end
			return 0
		end

		if @lastprice < @50DMA and @lastprice < @DWAP  and @lastPrice < @buyPrice * .92 --allow 8% loss (maybe catch a few that slipped through the 8% rule?)
			begin
				exec saveAudit @RunDate, 'Stock dropped below 50DMA and DWAP', @stockID
				exec addSell @buyID, @watchID, @RunDate, @shares, 'Stock dropped below 50DMA and DWAP'	
				Print 'Selling below 50DMA and DWAP'-- StockID:' + Convert(varchar, @stockID) + ' , BuyID:' + Convert(varchar,@BuyID) + ' , RunDate:' + Convert(varchar,@RunDate,101)
				return 1	
			end
		

		return 0
