-- SqlProcedure: [dbo].[getRecentTransactionsByMember]

set nocount on

create table #tval
(
stockID int,
ticker varchar(10),
companyname varchar(100),
transid int,
buyprice money,
sellprice money,
buydate datetime,
selldate datetime,
diff float null,
buycomment varchar(500),
sellcomment varchar(500)
)

declare @buydatestart datetime
select @buydatestart = AtWhenSubscribe
from Member
where MemberID = @MemberID

declare @realstart datetime, @realend datetime
select @realstart = Convert(datetime, convert(varchar,datepart(year, @startdate)) + '-' + convert(varchar,datepart(month, @startdate)) + '-' + convert(varchar,datepart(day, @startdate)))
select @realend = dateadd(day,1, @realstart)


insert into #tval
select sb.stockID, s.ticker, s.companyname, sb.BuyID, sd1.price, sd2.price,sd1.atwhen, sd2.atwhen, null, sb.comment, ss.comment  from StockBuy sb
inner join StockSell ss on ss.BuyID = sb.BuyID
inner join stockdata sd1 on sd1.stockID = sb.stockID and sd1.atwhen=sb.atwhen
inner join stockdata sd2 on sd2.stockID = sb.stockID and sd2.atwhen=ss.atwhen
inner join stock s on s.stockID = sb.stockID
where sd1.stockID = sd2.stockID
and s.active=1
and ss.atwhen between @realstart and @realend
and sb.atwhen >= @buydatestart

/*
insert into #tval
select st.stockID, s.ticker, s.companyname, st.transactionID, sd1.price, sd2.price,sd1.atwhen, sd2.atwhen, null, st.buycomment, st.sellcomment  from stocktransaction st
inner join stockdata sd1 on sd1.stockID = st.stockID and sd1.atwhen=st.atwhenbuy
inner join stockdata sd2 on sd2.stockID = st.stockID and sd2.atwhen=st.atwhensell
inner join stock s on s.stockID = st.stockID
where watchIDsell is not null
and sd1.stockID = sd2.stockID
and s.active=1
and st.atwhensell between @realstart and @realend
and st.atwhenbuy >= @buydatestart
--and st.status = 'S'
*/

/*
update #tval
set diff = convert(float,buyprice/sellprice)*100
where sellprice < buyprice
*/
update #tval
set diff = convert(float,sellprice/buyprice)
--where sellprice > buyprice

select distinct * from #tval

drop table #tval

set nocount off
