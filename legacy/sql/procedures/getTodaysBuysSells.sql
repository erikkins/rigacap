-- SqlProcedure: [dbo].[getTodaysBuysSells]

set nocount on

	select StockBuy.buyID, 'B' as Action, s.ticker from StockBuy inner join stock s on s.stockID=StockBuy.stockID where StockBuy.atwhen = @atwhen
	union
	select StockSell.buyID, 'S' as Action, s.ticker from StockSell inner join stockBuy sb on sb.buyID=StockSell.buyID inner join Stock s on s.stockID=sb.stockID where StockSell.atwhen = @atwhen
	

set nocount off
