-- SqlProcedure: [dbo].[rptLivingSpreadsheet]

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
buyID int
)

--these are the buys
insert into #ts
select s.stockID, ticker, 
case when ss.stockid is not null
	then companyname + ' (Split: ' + ss.Split + ')'
else
	companyname
end as companyname, 
sb.Shares, Convert(varchar,sb.DwapDate,101), sd3.Price , Convert(varchar,sb.AtWhen,101) BuyDate, sd1.Price BuyPrice, sd1.Volume BuyVolume,null, null, lastPrice, Convert(money,(sb.shares/100.00)*lastPrice) PresentValue,
Convert(decimal(6,1),Convert(decimal(5,1),lastprice)/convert(decimal(5,1),sd1.Price)*100)-100 PercentChangeFromBuy, datediff(day,sb.AtWhen, getdate()) DaysHeld,
'=HYPERLINK("http://www.abecap.com/dosell.aspx?bid=' + Convert(varchar,sb.buyID) + '&dt=' + replace(Convert(varchar,max(sd2.atwhen),101),'/','%2F') + '","Sell")',
sb.BuyID
from Stock s
inner join StockBuy sb on sb.StockID = s.StockID
inner join StockData sd1 on sd1.StockID = s.StockID
inner join StockData sd2 on sd2.StockID = s.StockID
left outer join StockData sd3 on sd3.stockID = s.StockID and sd3.Atwhen=s.LastDwapDate
left outer join StockSplit ss on ss.stockID=s.StockID and ss.ApplyDate is not null and ss.Atwhen between sb.Atwhen and @today
where sd1.atwhen = sb.atwhen
and sd2.Price = LastPrice
and sb.Status=0
and sb.channel = @channel
and s.active=1
group by s.StockID, s.Ticker, s.CompanyName,sb.Shares,sb.DwapDate,sd3.Price, sb.AtWhen, sd1.Price, sd1.Volume, s.LastPrice, sb.BuyID, ss.stockID, ss.split, sb.buyID
order by PercentChangeFromBuy desc

--now we need to see if we have any splits!
/*
declare @minbuydate datetime
declare @splitdate datetime, @split varchar(50)
select @minbuydate = min(BuyDate) from #ts
declare @today datetime
select @today = dateadd(day,1,getdate())
if exists (select * from StockSplit ss inner join #ts on ss.stockID = #ts.stockID where ss.atWhen between @minbuydate and @today)
	begin
		declare @sid int, @bdate datetime		
		--we have atleast one row
		declare splcur cursor for
			select #ts.stockID, buydate, ss.AtWhen, ss.split from #ts inner join StockSplit ss on ss.stockID=#ts.stockID where ss.atwhen between @minbuydate and @today
		open splcur
			fetch next from splcur into @sid, @bdate, @splitdate, @split
				while @@fetch_status=0
					begin
						if @splitdate > @bdate
							begin						
								update #ts
								set CompanyName = CompanyName + '(S ' + @split + ')'																
								where stockID = @sid			
							end
						fetch next from splcur into @sid, @bdate, @splitdate, @split
					end
		close splcur
		deallocate splcur
	end
*/



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
			select @50DMA = dbo.fn50DMA(@stockID, @buyDate)

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
		select * from #ts order by [%Δ] desc
	end
else
	begin
		select * from #ts order by ticker asc
	end
drop table #ts


create table #tss
(
stockID int,
ticker varchar(10),
companyname varchar(100),
LastDWAPDate varchar(20),
DWAPPrice money,
BuyDate varchar(20), 
BuyPrice money,
Shares decimal(8,2),
DaysHeld int,
DateSold varchar(20),
SellPrice money,
SellValue money,
[%Δ] decimal,
AdjBuyPrice money,
Comment varchar(500),
BuyID int
)

--these are the sells
if @orderbyTicker = 0
	begin
		insert into #tss
		select s.stockID, ticker, 
		case when ssp.stockid is not null
			then companyname + ' (Split: ' + ssp.Split + ')'
		else
			companyname
		end as companyname, 
		Convert(varchar,sb.DwapDate,101) as LastDWAPDate, sd3.Price, Convert(varchar,sb.AtWhen,101) BuyDate, sd1.Price BuyPrice,  ss.Shares,
		datediff(day,sb.AtWhen, ss.atwhen) DaysHeld, Convert(varchar,ss.AtWhen,101) DateSold, sd2.Price SellPrice, (ss.shares/100.00)* sd2.Price SellValue,
		Convert(decimal(6,1),Convert(decimal(5,1),sd2.Price)/convert(decimal(5,1),sd1.Price)*100)-100 PercentChange,
		(ss.shares/100.00)* sd1.Price AdjBuyPrice, ss.Comment, sb.BuyID
		from Stock s
		inner join StockBuy sb on sb.StockID = s.StockID
		inner join StockSell ss on ss.BuyID = sb.BuyID
		inner join StockData sd1 on sd1.StockID = s.StockID
		inner join StockData sd2 on sd2.StockID = s.StockID
		inner join StockData sd3 on sd3.stockID=s.stockID and sd3.atwhen=s.LastDwapDate
		left outer join StockSplit ssp on ssp.stockID=s.StockID and ssp.ApplyDate is not null and ssp.Atwhen between sb.Atwhen and ss.Atwhen
		where sd1.atwhen = sb.atwhen
		and ss.atwhen = sd2.atWhen
		and sb.channel = @channel
		group by s.stockID, ticker, ssp.stockID, s.CompanyName, sb.DWAPDate, sd3.price,sb.atwhen,sd1.price,ss.shares,ss.atwhen,sd2.price,ss.comment, ssp.split, sb.BuyID
		order by PercentChange desc
	end
else
	begin
		insert into #tss
		select s.stockID, ticker, 
		case when ssp.stockid is not null
			then companyname + ' (Split: ' + ssp.Split + ')'
		else
			companyname
		end as companyname, 
		Convert(varchar,sb.DwapDate,101) as LastDWAPDate, Convert(varchar,sb.AtWhen,101) BuyDate, sd1.Price BuyPrice,  ss.Shares,
		datediff(day,sb.AtWhen, ss.atwhen) DaysHeld, Convert(varchar,ss.AtWhen,101) DateSold, sd2.Price SellPrice, (ss.shares/100.00)* sd2.Price SellValue,
		Convert(decimal(6,1),Convert(decimal(5,1),sd2.Price)/convert(decimal(5,1),sd1.Price)*100)-100 PercentChange,
		(ss.shares/100.00)* sd1.Price AdjBuyPrice, ss.Comment, sb.BuyID
		from Stock s
		inner join StockBuy sb on sb.StockID = s.StockID
		inner join StockSell ss on ss.BuyID = sb.BuyID
		inner join StockData sd1 on sd1.StockID = s.StockID
		inner join StockData sd2 on sd2.StockID = s.StockID
		left outer join StockSplit ssp on ssp.stockID=s.StockID and ssp.ApplyDate is not null and ssp.Atwhen between sb.Atwhen and ss.Atwhen
		where sd1.atwhen = sb.atwhen
		and ss.atwhen = sd2.atWhen
		and sb.channel = @channel
		group by s.stockID, ticker, ssp.stockID, s.CompanyName, sb.DWAPDate,sb.atwhen,sd1.price,ss.shares,ss.atwhen,sd2.price,ss.comment, ssp.split, sb.BuyID
		order by ticker asc
	end

/*
select @minbuydate = min(BuyDate) from #tss
if exists (select * from StockSplit ss inner join #tss on ss.stockID = #tss.stockID where ss.atWhen between @minbuydate and @today)
	begin
		--we have atleast one row
		declare splcur cursor for
			select #tss.stockID, buydate, ss.AtWhen, ss.split from #tss inner join StockSplit ss on ss.stockID=#tss.stockID where ss.atwhen between @minbuydate and @today
		open splcur
			fetch next from splcur into @sid, @bdate, @splitdate, @split
				while @@fetch_status=0
					begin
						if @splitdate > @bdate
							begin								
						
								update #tss
								set CompanyName = CompanyName + '(S ' + @split +  ')'								
								where stockID = @sid			
							end
						fetch next from splcur into @sid, @bdate, @splitdate, @split
					end
		close splcur
		deallocate splcur
	end
*/

	select * from #tss
	order by [%Δ] desc
	
	drop table #tss

set nocount off
