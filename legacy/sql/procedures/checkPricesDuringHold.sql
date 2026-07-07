-- SqlProcedure: [dbo].[checkPricesDuringHold]

set nocount on
declare @buyID int
declare @buydate datetime, @selldate datetime
declare @buyPrice money

select @buydate = Atwhen, @buyid=buyid
from stockbuy where channel='d' and stockID=@StockID

select @buyprice =Price from stockData
where stockID=@stockID
and atwhen=@BuyDate

select @selldate = atwhen
from stocksell
where buyID=@buyID

if @selldate is null
	select @selldate = getdate()

select atwhen, Price, Volume, ((Price/@buyprice)*100)-100 [% Change] from stockdata
where stockID=@stockID
and atwhen between @buydate and @selldate

set nocount off
