-- SqlProcedure: [dbo].[getDataByStockDT]

set nocount on
/*
create table #tdata
(
atwhen varchar(20),
price money,
volume bigint,
DWAP money,
[200DMA] money,
[50DMA] money,
Split varchar(10),
DWAPDate bit
)
*/

		--insert into #tdata
		select Convert(varchar,sd.atwhen,101) as atwhen, sd.price, sd.volume, 
		--dbo.fnDWAP(sd.stockID,sd.atwhen)[DWAP], 
		sd.dwap [DWAP],
		sd.dwap200 [DWAP200],
		dbo.fn200DMA(sd.stockID, sd.atwhen)[200DMA], 
		dbo.fn50DMA(sd.stockID, sd.atwhen)[50DMA], 
		case when ss.split is null then null else ss.split end as Split,
		dbo.fnIsPriceCrossDWAP(sd.stockID, sd.atwhen)[DWAPDate]
		from StockData sd
		left outer join stocksplit ss on ss.stockID=sd.stockID and ss.atwhen=sd.atwhen and ss.applydate is not null
		where sd.stockID = @stockID
		and sd.atwhen between @startdate and @enddate
		group by sd.stockID, sd.atwhen, sd.price, sd.volume,ss.split, sd.dwap, sd.dwap200
		order by sd.atwhen asc

		/*
		update #tdata
		set DWAPDate = case when nd.atwhen=#tdata.atwhen then 1 else 0 end
		from NewDwap nd
		where nd.stockID=@StockID
		and nd.atwhen=#tdata.atwhen
		*/
/*
select * from #tdata
drop table #tdata
*/
