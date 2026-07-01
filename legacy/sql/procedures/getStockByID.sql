-- SqlProcedure: [dbo].[getStockByID]

set nocount on

	select s.stockID, s.ticker,s.CompanyName, s.Active, s.Exchange, s.Industry,
	dbo.LastPrice(@stockID) as LastPrice,
	dbo.get52WeekHigh(@stockID) as [52WeekHigh],
	dbo.get52WeekHighDate(@stockID) as [52WeekHighDate]
	from stock s
	where s.stockID = @stockID


set nocount off
