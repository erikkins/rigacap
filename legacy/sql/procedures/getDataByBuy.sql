-- SqlProcedure: [dbo].[getDataByBuy]

set nocount on

declare @startdate datetime
select @startdate = case when DWAPDate is null then DateAdd(month,-3,AtWhen) else dateadd(day,-14,DWAPDate) end
from stockbuy
where buyID=@BuyID

if not exists (select top 1 * from buycache where buyID=@buyID)
	begin

		insert into buycache (BuyID,atwhen,price,volume,dwap,[200DMA],[50DMA], split,bought,dwapdate,sold,dwapdata,[200Volume],DWAP50,low,high)
		select @BuyID, 
		Convert(varchar,sd.atwhen,101) as atwhen, 
		sd.price, 
		sd.volume, 
		NULL as DWAP, 
		dbo.fn200DMA(sd.stockID, sd.atwhen)[200DMA], 
		dbo.fn50DMA(sd.stockID, sd.atwhen)[50DMA], 
		ss.split, 
		case when sb.atwhen=sd.atwhen then 1 else 0 end as Bought, 
		case when sb.DWAPDate=sd.atwhen then 1 else 0 end as DWAPDate, 
		case when ssl.atwhen=sd.atwhen then ssl.comment else null end as Sold,
		dbo.fnDWAP(sd.stockID, sd.atwhen) [DWAPData],
		dbo.fn200Volume(sd.stockID,sd.atwhen) [200Volume],
		dbo.fnDWAP50(sd.stockID, sd.atwhen)[DWAP50],
		sd.daylow low,
		sd.dayhigh high
		from StockData sd
		left join stocksplit ss on ss.stockID=sd.stockID and ss.atwhen=sd.atwhen and ss.applydate is not null
		Inner join stockbuy sb on sb.stockID = sd.stockID
		left join stocksell ssl on ssl.buyID = sb.buyID
		where sb.buyID=@buyID
		and sd.atwhen between @startdate and case when ssl.atwhen is not null then dateadd(month,3,ssl.atwhen) else getdate() end --dateadd(day,14,ssl.atwhen) else getdate() end
		group by sd.stockID, sd.atwhen, sd.price, sd.volume, ss.split, sb.atwhen, ssl.atwhen, ssl.comment, sb.DWAPDate, sd.daylow, sd.dayhigh
		order by sd.atwhen asc
	end
if @silent = 0
	BEGIN
		select atwhen as atwhen, price, volume, DWAP, [200DMA], [50DMA],split,bought,dwapdate,sold,dwapdata,[200Volume],[DWAP50], low,high
		from buycache 
		where BuyID = @BuyID
		order by atwhen asc
	END
/*
select Convert(varchar,sd.atwhen,101) as atwhen, sd.price, sd.volume, NULL as DWAP, AVG(sd1.price)[200DMA], AVG(sd2.price)[50DMA], ss.split, 
case when sb.atwhen=sd.atwhen then 1 else 0 end as Bought, 
case when sb.DWAPDate=sd.atwhen then 1 else 0 end as DWAPDate, 
case when ssl.atwhen=sd.atwhen then ssl.comment else null end as Sold
from StockData sd
inner join StockData sd1 on sd1.stockID=sd.stockID
inner join StockData sd2 on sd2.stockID=sd.stockID
left join stocksplit ss on ss.stockID=sd.stockID and ss.atwhen=sd.atwhen and ss.applydate is not null
Inner join stockbuy sb on sb.stockID = sd.stockID
left join stocksell ssl on ssl.buyID = sb.buyID
where sb.buyID=@buyID
and sd.atwhen between dateadd(day,-14,sb.dwapdate) and case when ssl.atwhen is not null then dateadd(day,14,ssl.atwhen) else getdate() end
and sd1.atwhen between dateadd(day,-200,sd.atwhen) and sd.atwhen
and sd2.atwhen between dateadd(day,-50,sd.atwhen) and sd.atwhen
group by sd.stockID, sd.atwhen, sd.price, sd.volume, ss.split, sb.atwhen, ssl.atwhen, ssl.comment, sb.DWAPDate
order by sd.atwhen asc
*/
