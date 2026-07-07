-- SqlProcedure: [dbo].[getClosedTransactions]

set nocount on

create table #tval
(
stockID int,
ticker varchar(10),
companyname varchar(100),
transid int,
buyprice money,
buydate datetime,
sellprice money,
selldate datetime,
buycomment varchar(500),
sellcomment varchar(500),
lastPrice money,
daysheld int
)

declare @realstart datetime, @realend datetime
select @realstart = Convert(varchar,@startdate,101)
--Convert(datetime, convert(varchar,datepart(year, @startdate)) + '-' + convert(varchar,datepart(month, @startdate)) + '-' + convert(varchar,datepart(day, @startdate)))
select @realend = dateadd(day,1, @realstart)

insert into #tval
select sb.stockID, s.ticker, s.companyname, sb.buyID, sd1.price, sd1.atwhen, sd2.price, sd2.atwhen, sb.comment,ss.comment, s.LastPrice, datediff(day, sb.AtWhen, getdate())  
from StockBuy sb
inner join stockdata sd1 on sd1.stockID = sb.stockID and sd1.atwhen=sb.atwhen
inner join stock s on s.stockID = sb.stockID and s.stockID=sd1.stockID
inner join stockSell ss on ss.BuyID=sb.BuyID
inner join stockdata sd2 on sd2.stockID=sb.stockID and sd2.atwhen=ss.atwhen
where s.active=1
and ss.atwhen = @realstart 
and sb.channel='C'


/*
select st.stockID, s.ticker, s.companyname, st.transactionID, sd1.price, sd1.atwhen, st.buycomment, st.sellcomment, s.LastPrice, datediff(day, st.AtWhenBuy, getdate())  from stocktransaction st
inner join stockdata sd1 on sd1.stockID = st.stockID and sd1.atwhen=st.atwhenbuy
inner join stock s on s.stockID = st.stockID and s.stockID=sd1.stockID
where watchIDsell is null
and s.active=1
and st.atwhenbuy = @realstart
*/

select distinct * from #tval
order by companyname
drop table #tval

set nocount off
