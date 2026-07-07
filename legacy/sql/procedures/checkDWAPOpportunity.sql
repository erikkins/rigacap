-- SqlProcedure: [dbo].[checkDWAPOpportunity]

set nocount on

declare @lastDWAPDate datetime
declare @dwapprice money

select @lastDWAPDate = LastDWAPDate
from Stock
where stockID=@stockID

select @dwapprice = price
from stockdata
where stockID=@stockID
and atwhen = @lastdwapdate

select sd.atwhen, sd.price, sd.volume, ((sd.price/@dwapprice)*100)-100 [% Change],
avg(sd2.volume) [200DMAVolume]
from stockdata sd
left join stockdata sd2 on sd2.stockID=sd.stockID and sd.atwhen=sd2.atwhen
where sd.stockID=@StockID
and sd.atwhen >= @lastDWAPDate
and sd2.atwhen between dateadd(day,-200,sd.atwhen) and sd.atwhen
group by sd.atwhen, sd.price, sd.volume,((sd.price/@dwapprice)*100)-100
order by sd.atwhen asc

set nocount off
