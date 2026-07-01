-- SqlProcedure: [dbo].[getOpenTransactions]

set nocount on

create table #tval
(
stockID int,
ticker varchar(10),
companyname varchar(100),
transid int,
buyprice money,
buydate datetime,
buycomment varchar(500),
sellcomment varchar(500),
lastPrice money,
daysheld int,
which varchar(10)
)

declare @realstart datetime, @realend datetime
select @realstart = Convert(datetime, convert(varchar,datepart(year, @startdate)) + '-' + convert(varchar,datepart(month, @startdate)) + '-' + convert(varchar,datepart(day, @startdate)))
select @realend = dateadd(day,1, @realstart)

insert into #tval
select sb.stockID, s.ticker, s.companyname, sb.buyID, sd1.price, sd1.atwhen, sb.comment,null, s.LastPrice, datediff(day, sb.AtWhen, getdate()),
case when sb.Channel='A' then 'A,B,C' else sb.channel end
from StockBuy sb
inner join stockdata sd1 on sd1.stockID = sb.stockID and sd1.atwhen=sb.atwhen
inner join stock s on s.stockID = sb.stockID and s.stockID=sd1.stockID
where s.active=1
and sb.atwhen = @realstart
and sb.status = 0
and sb.channel IN ('A','D', 'E', 'F')


--now get any reiterations
/*
insert into #tval
select s.StockID, s.ticker, s.companyname, null, s.LastPrice, null, 'REITERATE', null, s.LastPrice,0
from StockAudit sa
inner join Stock s on s.stockID = sa.stockID
where sa.atwhen = @realstart
and sa.event='REITERATE'
*/


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
