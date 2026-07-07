-- SqlProcedure: [dbo].[getStockByTicker]

set nocount on
	select * from stock
	where Ticker = @Ticker
set nocount off
