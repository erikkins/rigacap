-- SqlProcedure: [dbo].[getOldestOpenTransaction]
-- header:
-- CREATE proc [dbo].[getOldestOpenTransaction]

CREATE proc [dbo].[getOldestOpenTransaction]
as
set nocount on

select min(atwhen)
from StockBuy
where status = 0

/*
select min(atwhenbuy)
from StockTransaction
where atwhensell is null 
*/
set nocount off
