-- SqlProcedure: [dbo].[GetActiveStocks]
-- header:
-- CREATE proc [dbo].[GetActiveStocks]

CREATE proc [dbo].[GetActiveStocks]
as
set nocount on

/*
Active (Current) = 1
Active (<$10) = 0
Inactive = 99
*/

select * from Stock
where active!=99
order by CompanyName, Ticker

set nocount off
