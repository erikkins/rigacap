-- SqlProcedure: [dbo].[getData]

set nocount on

select Convert(varchar,sd.atwhen,101) as atwhen, sd.price, sd.volume, NULL as DWAP, AVG(sd1.price)[200DMA], AVG(sd2.price)[50DMA], ss.split, 
case when sb.atwhen=sd.atwhen then 1 else 0 end as Bought, 
case when sb.DWAPDate=sd.atwhen then sb.DWAPDate else NULL end as DWAPDate, 
case when ssl.atwhen=sd.atwhen then ssl.comment else null end as Sold
from StockData sd
inner join StockData sd1 on sd1.stockID=sd.stockID
inner join StockData sd2 on sd2.stockID=sd.stockID
left join stocksplit ss on ss.stockID=sd.stockID and ss.atwhen=sd.atwhen and ss.applydate is not null
left join stockbuy sb on sb.stockID = sd.stockID
left join stocksell ssl on ssl.buyID = sb.buyID
where sd.stockID=@stockID
and sd.atwhen between @startdate and dateadd(day,1,@enddate)
and sd1.atwhen between dateadd(day,-200,sd.atwhen) and sd.atwhen
and sd2.atwhen between dateadd(day,-50,sd.atwhen) and sd.atwhen
group by sd.stockID, sd.atwhen, sd.price, sd.volume, ss.split, sb.atwhen, ssl.atwhen, ssl.comment, sb.DWAPDate
order by sd.atwhen asc

set nocount off
