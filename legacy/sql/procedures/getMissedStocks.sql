-- SqlProcedure: [dbo].[getMissedStocks]
-- header:
-- CREATE proc [dbo].[getMissedStocks] as

CREATE proc [dbo].[getMissedStocks] as
set nocount on
	select distinct ticker, msd.stockID, count(*) from missedstockdata msd
	inner join stock s on s.stockID=msd.stockID
	where s.active=1
	group by msd.stockID, s.ticker
	order by count(*) desc
set nocount off
