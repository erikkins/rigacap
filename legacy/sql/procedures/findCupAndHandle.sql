-- SqlProcedure: [dbo].[findCupAndHandle]

set nocount on
--is today's price higher than the handle high
declare @todayprice money
declare @handlehigh money
declare @handlestart datetime, @handleend datetime
declare @oldhighdate datetime, @oldhigh money

--find a date where the price is >=20% of a price later


/*
select @oldhighdate = atwhen, @oldhigh = max(price)
from stockdata sd
where stockID = @stockID
and price > 1.2 * (select avg(price) from stockdata sd2 where sd2.stockID=@stockID and sd2.atwhen between dateadd(month,-6,sd.atwhen) and sd.atwhen)
and atwhen < @atwhen
and atwhen < (select top 1 atwhen from stockdata sd3 where sd3.stockID=@stockID and sd3.atwhen > sd.atwhen and sd3.price < (sd.Price * .9))
group by price, atwhen
*/
select @oldhighdate = max(atwhen)
from stockdata sd
where stockID = @stockID
and price > 1.3 * (select avg(price) from stockdata sd2 where sd2.stockID=@stockID and sd2.atwhen between dateadd(month,-6,sd.atwhen) and dateadd(month,-2,sd.atwhen)) --30% upswing
and atwhen < @atwhen
and atwhen < (select top 1 atwhen from stockdata sd3 where sd3.stockID=@stockID and sd3.atwhen > sd.atwhen and sd3.price < (sd.Price * .8)) -- 20% correction

select @oldhigh = price
from stockdata
where stockID=@stockID
and atwhen = @oldhighdate

select @handlestart = min(atwhen)
from stockdata
where stockID=@stockID
and atwhen between dateadd(week,7,@oldhighdate) and @atwhen
and price >= (@oldhigh * .85) --handle rises within 15% of old high

select @handlehigh = price
from stockdata
where stockID=@stockID
and atwhen=@handlestart

declare @handledown datetime, @handledownprice money

select @handledown = min(atwhen)
from stockdata
where stockID=@stockID
and atwhen > dateadd(week,1,@handlestart)
and price < (@handlehigh * .92)--8%

select @handledownprice = price
from stockdata sd
where stockID=@stockID
and atwhen = @handledown


declare @buydate datetime, @buyprice money
select @buydate = min(atwhen)
from stockdata
where stockID=@stockID
and atwhen > @handledown
and price > @handlehigh
and volume >= (1.5 * dbo.fn50Volume(@stockID,atwhen))

select @buyprice = price
from stockdata
where stockID= @stockID
and atwhen = @buydate

--select @oldhighdate oldhighdate, @oldhigh oldhigh, @handlestart handlestart, @handlehigh handlend, @handledown handledown, @handledownprice handledownprice, @buydate BUYDATE, @buyprice BUYPRICE
declare @ticker varchar(10)
if @buydate is not null and @buyprice is not null
	begin
		select @ticker = ticker from stock where stockID=@stockID
		insert into ##tcah
		select @stockID stockID, @ticker ticker, @buydate buydate, @buyprice buyprice
		--Print 'FOUND StockID:' + convert(varchar,@stockID) + ' (' + @ticker + ')on ' + convert(varchar,@buydate,101) + ' for $' + convert(varchar,@buyprice)

	end

set nocount off
