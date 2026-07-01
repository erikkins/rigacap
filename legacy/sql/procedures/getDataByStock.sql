-- SqlProcedure: [dbo].[getDataByStock]

set nocount on

declare @startdate datetime
select @startdate = '1/1/2007'

	if exists (select top 1 * from stockcache where stockID=@stockID and channel=@channel)
		begin
			select * from stockcache where stockID=@stockID and channel=@channel order by convert(datetime,atwhen) asc
			return
		end
	else


		insert into StockCache
		select @stockID, Convert(varchar,sd.atwhen,101) as atwhen, sd.price, sd.volume, 
		dbo.fnDWAP(sd.stockID,sd.atwhen)[DWAP], 
		dbo.fn200DMA(sd.stockID, sd.atwhen)[200DMA], 
		dbo.fn50DMA(sd.stockID, sd.atwhen)[50DMA], 
		case when ss.split is null then null else ss.split end as Split,
		dbo.fnIsPriceCrossDWAP(sd.stockID, sd.atwhen),
		0,
		0,
		@channel
		from StockData sd
		left outer join stocksplit ss on ss.stockID=sd.stockID and ss.atwhen=sd.atwhen and ss.applydate is not null
		where sd.stockID = @stockID
		and sd.atwhen between @startdate and getdate()
		group by sd.stockID, sd.atwhen, sd.price, sd.volume,ss.split
		order by sd.atwhen asc
		/*
		update #tdata
		set DWAPDate = case when nd.atwhen=#tdata.atwhen then 1 else 0 end
		from NewDwap nd
		where nd.stockID=@StockID
		and nd.atwhen=#tdata.atwhen
		*/

	select * from stockcache where stockID=@stockID and channel=@channel order by convert(datetime,atwhen) asc
/*
if @DWAPOnly=0
	begin
		update #tdata
		set Bought= case when sb.atwhen=#tdata.atwhen then 1 else 0 end
		from StockBuy sb 
		where sb.atwhen=#tdata.atwhen and sb.stockID=@stockID
		and sb.channel=@channel

		update #tdata
		set Sold= case when ss.atwhen=#tdata.atwhen then 1 else 0 end
		from StockBuy sb 
		inner join StockSell ss on ss.buyID=sb.BuyID
		where ss.atwhen=#tdata.atwhen and sb.stockID=@stockID
		and sb.channel=@channel
	end
*/
--select * from StockCache
--drop table #tdata



/*
select Convert(varchar,sd.atwhen,101) as atwhen, sd.price, sd.volume, 
dbo.fnDWAP(sd.stockID,sd.atwhen)[DWAP], 
dbo.fn200DMA(sd.stockID, sd.atwhen)[200DMA], 
dbo.fn50DMA(sd.stockID, sd.atwhen)[50DMA], 
ss.split,
case when sb.atwhen=sd.atwhen then 1 else 0 end as Bought,
case when sb.DWAPDate=sd.atwhen then 1 else 0 end as DWAPDate,
case when ssl.atwhen=sd.atwhen then 1 else 0 end as Sold
from StockData sd
left join stocksplit ss on ss.stockID=sd.stockID and ss.atwhen=sd.atwhen and ss.applydate is not null
left join StockBuy sb on sb.StockID=sd.StockID and sb.atwhen=sd.atwhen
left join StockSell ssl on ssl.BuyID=sb.BuyID
where sd.stockID = @stockID
and sd.atwhen between @startdate and getdate()
group by sd.stockID, sd.atwhen, sd.price, sd.volume, ss.split, sb.AtWhen, sb.DWAPDate, ssl.AtWhen
order by sd.atwhen asc
*/
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
