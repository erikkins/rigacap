-- SqlProcedure: [dbo].[rptLivingSells]

set nocount on

create table #tss
(
stockID int,
ticker varchar(50),
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
BuyID int,
Channel char(1),
CacheDate datetime null
)

if exists (select * from SellCache where channel=@channel and CacheDate = convert(varchar, getdate(), 101))
	begin
		insert into #tss
			select * from SellCache where channel=@channel and CacheDate= convert(varchar, getdate(), 101)
	end
else
	begin
		--these are the sells
		if @orderbyTicker = 0
			begin
				insert into #tss
				select s.stockID, 
				s.Ticker,	--case when dbo.DoBuy(sb.BuyID) = 0 then '<div bgcolor=red>' + ticker + '</div>' else  '<div bgcolor=green>' + ticker + '</div>' end as Ticker,		
				case when ssp.stockid is not null
					then companyname + ' (Split: ' + ssp.Split + ')'
				else
					companyname
				end as companyname, 
				case when sb.dwapdate is null then '' 
				else Convert(varchar,sb.DwapDate,101) end as LastDWAPDate,
				sd3.Price, Convert(varchar,sb.AtWhen,101) BuyDate, sd1.Price BuyPrice,  ss.Shares,
				datediff(day,sb.AtWhen, ss.atwhen) DaysHeld, Convert(varchar,ss.AtWhen,101) DateSold, sd2.Price SellPrice, (ss.shares/100.00)* sd2.Price SellValue,
				Convert(decimal(6,1),Convert(decimal(5,1),sd2.Price)/convert(decimal(5,1),sd1.Price)*100)-100 PercentChange,
				(ss.shares/100.00)* sd1.Price AdjBuyPrice, ss.Comment, sb.BuyID, @channel, convert(varchar, getdate(), 101)
				--(ss.shares/100.00)* sd1.Price AdjBuyPrice, case when sb.BuyIDLink is null then ss.Comment else ss.comment + ' after ' + ss2.comment end, sb.BuyID
				from Stock s
				inner join StockBuy sb on sb.StockID = s.StockID
				inner join StockSell ss on ss.BuyID = sb.BuyID
				inner join StockData sd1 on sd1.StockID = s.StockID --buyprice info
				inner join StockData sd2 on sd2.StockID = s.StockID --sellprice info
				left outer join StockData sd3 on sd3.stockID=s.stockID and sd3.atwhen=sb.DwapDate --dwap price info
				left outer join StockSplit ssp on ssp.stockID=s.StockID and ssp.ApplyDate is not null and ssp.Atwhen between sb.Atwhen and ss.Atwhen
				left outer join StockBuy sb2 on sb2.BuyID=sb.BuyIDLink
				--left outer join StockSell ss2 on ss2.BuyID = sb2.BuyID
				where sd1.atwhen = sb.atwhen
				and ss.atwhen = sd2.atWhen
				and sb.channel = @channel
				and s.Active=1			
				
				--and dbo.fnIsTightLines(sb.StockID,sb.atwhen) = 1
				--and dbo.IsAccumulation(sb.stockID,sb.atwhen) = 1
				--and dbo.IsVolumeAboveAverage(sb.stockID, sb.atwhen) = 1

				--and sb.dwapdate is not null
				group by s.stockID, ticker, ssp.stockID, s.CompanyName, sb.DWAPDate, sd3.price,sb.atwhen,sd1.price,ss.shares,ss.atwhen,sd2.price,ss.comment, ssp.split, sb.BuyID, sb.BuyIDLink--, ss2.Comment
				--order by PercentChange desc
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
				(ss.shares/100.00)* sd1.Price AdjBuyPrice, ss.Comment, sb.BuyID, @channel, convert(varchar, getdate(), 101)
				from Stock s
				inner join StockBuy sb on sb.StockID = s.StockID
				inner join StockSell ss on ss.BuyID = sb.BuyID
				inner join StockData sd1 on sd1.StockID = s.StockID
				inner join StockData sd2 on sd2.StockID = s.StockID
				left outer join StockSplit ssp on ssp.stockID=s.StockID and ssp.ApplyDate is not null and ssp.Atwhen between sb.Atwhen and ss.Atwhen
				where sd1.atwhen = sb.atwhen
				and ss.atwhen = sd2.atWhen
				and sb.channel = @channel
				and s.active=1
				group by s.stockID, ticker, ssp.stockID, s.CompanyName, sb.DWAPDate,sb.atwhen,sd1.price,ss.shares,ss.atwhen,sd2.price,ss.comment, ssp.split, sb.BuyID
				order by ticker asc
			end

	end
	if @startdate is not null and @enddate is not null
		begin
			select * from #tss
			where buydate between @startdate and @enddate
			and DateSold < @enddate
			order by [%Δ] desc
		end
	else
		begin
			select * from #tss
			order by [%Δ] desc
		end

	delete from SellCache
	insert into SellCache
		select * from #tss

	drop table #tss

set nocount off
