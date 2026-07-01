-- SqlProcedure: [dbo].[getLastValue]

set nocount on
	select @LastValue = price 
	from StockData
	where stockID = @StockID
	and AtWhen = (select max(atwhen) from stockdata where stockid=@stockID)
set nocount off
