-- SqlProcedure: [dbo].[rptLivingBuys]

set nocount on

declare @today datetime
select @today=getdate()

create table #ts
(
stockID int,
ticker varchar(10),
companyname varchar(100),
Shares decimal(8,2),
LastDWAP varchar(20),
DWAPPrice money,
BuyDate varchar(20), 
BuyPrice money,
BuyVolume int,
[Buy50DMA%] decimal,
YesterdayPrice money,
LastPrice money,
PresentValue money,
[%Δ] decimal,
DaysHeld int,
link varchar(200),
buyID int,
Channel char(1)
)

--these are the buys
insert into #ts
select s.stockID, ticker, 
case when ss.stockid is not null
	then companyname + ' (Split: ' + ss.Split + ')'
else
	companyname
end as companyname, 
sb.Shares, case when sb.dwapdate is null then 'Rebuy' else Convert(varchar,sb.DwapDate,101) end as DWAPDate, sd3.Price , Convert(varchar,sb.AtWhen,101) BuyDate, sd1.Price BuyPrice, sd1.Volume BuyVolume,null, null, dbo.lastPrice(s.stockID), Convert(money,(sb.shares/100.00)*lastPrice) PresentValue,
Convert(decimal(6,1),Convert(decimal(5,1),dbo.lastprice(s.stockID))/convert(decimal(5,1),sd1.Price)*100)-100 PercentChangeFromBuy, datediff(day,sb.AtWhen, getdate()) DaysHeld,
'=HYPERLINK("http://www.abecap.com/dosell.aspx?bid=' + Convert(varchar,sb.buyID) + '&dt=' + replace(Convert(varchar,max(sd2.atwhen),101),'/','%2F') + '","Sell")',
sb.BuyID, @channel
from Stock s
inner join StockBuy sb on sb.StockID = s.StockID
inner join StockData sd1 on sd1.StockID = s.StockID
inner join StockData sd2 on sd2.StockID = s.StockID
left outer join StockData sd3 on sd3.stockID = s.StockID and sd3.Atwhen=sb.DwapDate
left outer join StockSplit ss on ss.stockID=s.StockID and ss.ApplyDate is not null and ss.Atwhen between sb.Atwhen and @today
where sd1.atwhen = sb.atwhen
and sd2.Price = LastPrice
and sb.Status=0
and sb.channel = @channel
and s.active=1
--and sb.dwapdate is not null
group by s.StockID, s.Ticker, s.CompanyName,sb.Shares,sb.DwapDate,sd3.Price, sb.AtWhen, sd1.Price, sd1.Volume, s.LastPrice, sb.BuyID, ss.stockID, ss.split, sb.buyID
order by PercentChangeFromBuy desc

declare @50DMA money

declare @stockID int, @yprice money, @lastdate datetime, @sumvol float, @countvol int, @buydate datetime, @buyvol int,@avgvol int
declare upcur cursor for
	select stockID, BuyDate, BuyVolume from #ts

open upcur
fetch next from upcur into @stockID, @buydate, @buyvol
	while @@fetch_status=0
		begin
			select @lastdate = max(atwhen)
			from StockData
			where StockID = @StockID

			select @yprice = Price
			from StockData
			where StockID = @StockID
			and Atwhen = (select max(atwhen) from StockData where StockID = @StockID and atwhen < @lastdate)
			/*
			select @sumvol = sum(volume), @countvol = count(*)
			from StockData
			where StockID = @StockID
			and Atwhen between dateadd(day,-50,@buydate) and dateadd(day,1,@buydate)

			select @avgvol = @sumvol/@countvol		
			*/
			select @50DMA = dbo.fn50dma(@stockID, @buydate)

			update #ts
			set YesterdayPrice = @yprice,
			[Buy50DMA%] = @50DMA
			--[Buy50DMA%] = (@buyvol/convert(decimal,@avgvol))*100
			where StockID = @StockID

		fetch next from upcur into @stockID, @buydate, @buyvol
		end
close upcur
deallocate upcur
if @orderByTicker = 0
	begin
		if @startdate is not null and @enddate is not null
			begin
				select * from #ts 
				where BuyDate between @startdate and @enddate
				order by [%Δ] desc
			end
		else
			begin
				select * from #ts order by [%Δ] desc
			end
	end
else
	begin
		if @startdate is not null and @enddate is not null
			begin
				select * from #ts 
				where BuyDate between @startdate and @enddate
				order by ticker asc
			end
		else
			begin
				select * from #ts order by ticker asc
			end
	end
drop table #ts
