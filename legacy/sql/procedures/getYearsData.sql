-- SqlProcedure: [dbo].[getYearsData]

set nocount on

declare @dtl datetime, @dts varchar(20), @dte varchar(20)
select @EndDate = dateadd(day,-1,@EndDate)
select @dtl = dateadd(year,-1, @EndDate)
select @dts = convert(varchar, @dtl, 101)
select @dte = convert(varchar,@EndDate, 101)

/*
select convert(varchar,atwhen,101) as Date, Price as Low, Price as High, Price as [Close], Volume
from StockData
where atwhen between @dts and @dte
and stockID = @stockID
order by atwhen asc
*/
declare @tchart table
(
	Date varchar(20),
	Low money,
	High money,
	[Close] money,
	Volume float,
	week int,
	DWAP money,
	Buy varchar(500),
	Sell varchar(500),
	[50DMA] money,
	[200DMA] money,
	LastDWAPDate varchar(20)
)
insert into @tchart
select convert(varchar,sd.atwhen,101) as Date, sd.Price as Low, sd.Price as High, sd.Price as [Close], sd.Volume as Volume, 
DatePart(wk, sd.atwhen) as week, dc.DWAP, bd.Buy, bs.Sell, Null as [50DMA], Null as [200DMA], NULL as LastDWAPDate
from StockData sd
left join DataCache dc on dc.StockID = sd.StockID and dc.AtWhen = sd.Atwhen
left join
(
  select distinct Convert(varchar,sb.atwhen,101) + '--' + Convert(varchar,Price) + '|' + sb.Comment as Buy, sb.stockID, sb.atwhen from stockBuy sb	
  inner join StockData sd3 on sd3.StockID=sb.StockID and sd3.atwhen = sb.atwhen
) as bd on sd.stockID = bd.stockID and datepart(wk,bd.atwhen) = DatePart(wk, sd.atwhen) and datepart(year,bd.atwhen) = DatePart(year, sd.atwhen)
left join
(
  select distinct Convert(varchar,ss.atwhen,101) + '--' + Convert(varchar,Price) + '|' + ss.comment as sell, sb.stockID, ss.atwhen 
  from stockSell ss
  inner join StockBuy sb on sb.BuyID=ss.BuyID	
  inner join StockData sd4 on sd4.StockID=sb.StockID and sd4.atwhen = ss.atwhen
  where sb.Channel = 'C'
) as bs on sd.stockID = bs.stockID and datepart(wk,bs.atwhen) = DatePart(wk, sd.atwhen) and datepart(year,bs.atwhen) = DatePart(year, sd.atwhen)

/*
left join 
(	
	/*
  select sum(price)/50 as Price, sd50.StockID, atwhen
  from Stockdata sd50
  where sd50.stockid=@StockID and atwhen in (select top 50 sdt.atwhen from stockdata sdt where sdt.stockID=@stockID and sdt.atwhen <= sd50lj.atwhen)  
  group by StockID, atwhen
	*/
	select sum(sdx.price)/50 as Price, sd50.StockID, sd50.atwhen
	from Stockdata sd50
    inner join Stockdata sdx on sd50.stockID = sdx.stockID
	where sdx.atwhen <= sd50.atwhen
	group by sd50.StockID, sd50.atwhen
) as sd50lj on sd50lj.StockID=sd.stockID and sd50lj.atwhen=sd.atwhen
*/
where sd.atwhen between @dts and @dte
and sd.stockID = @stockID
and sd.atwhen = (select max(sd2.atwhen) from StockData sd2 where sd2.stockID=@stockID and DatePart(wk, sd2.atwhen) = DatePart(wk, sd.atwhen))
order by sd.atwhen asc

--now cursor through and build the 50 and 200 day moving averages
declare @tdate datetime
declare @tsum50 money, @tsum200 money, @lastDwapDate datetime

declare chcur cursor for
	select date from @tchart
open chcur
fetch next from chcur into @tdate
while @@fetch_status=0
	begin
		
		select @tsum50 = sum(price)/50
		from Stockdata sd50
		where sd50.stockid=@StockID and atwhen in (select top 50 sdt.atwhen from stockdata sdt where sdt.stockID=@stockID and sdt.atwhen <= @tdate order by atwhen desc)  		

		select @tsum200 = sum(price)/200
		from Stockdata sd50
		where sd50.stockid=@StockID and atwhen in (select top 200 sdt.atwhen from stockdata sdt where sdt.stockID=@stockID and sdt.atwhen <= @tdate order by atwhen desc)  

		select @LastDWAPDate = LastDWAPDate
		from Stock
		where StockID = @StockID

		if (datepart(wk, @LastDWAPDate) = datepart(wk, @tdate) and datepart(year,@LastDWAPDate) = datepart(year, @tdate))
			begin
				--do nothing	
				select @LastDWAPDate = @LastDWAPDate
			end
		else
			begin
				select @LastDWAPDate = null
			end

		update @tchart
		set [50DMA] = @tsum50, [200DMA] = @tsum200, LastDWAPDate = Convert(varchar,@LastDWAPDate,101)
		where Date = @tdate

	fetch next from chcur into @tdate
	end
close chcur
deallocate chcur

select * from @tchart

set nocount off
