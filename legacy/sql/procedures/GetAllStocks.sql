-- SqlProcedure: [dbo].[GetAllStocks]
-- header:
-- CREATE proc [dbo].[GetAllStocks]

CREATE proc [dbo].[GetAllStocks]
as
set nocount on

select * from Stock
order by CompanyName, Ticker

set nocount off
