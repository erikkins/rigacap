-- SqlProcedure: [dbo].[GetAllNewStocks]
-- header:
-- CREATE proc [dbo].[GetAllNewStocks]

CREATE proc [dbo].[GetAllNewStocks]
as
set nocount on

select * from Stock s
where not exists (select distinct stockID from stockdata sd where sd.stockID=s.stockID)
order by s.CompanyName, s.Ticker

set nocount off
