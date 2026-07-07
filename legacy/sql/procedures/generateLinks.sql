-- SqlProcedure: [dbo].[generateLinks]

set nocount on
declare @linx table
(
link varchar(8000)
)
declare @sid int, @tick varchar(10), @dt datetime, @p money, @v bigint
declare @atwhenup datetime, @price2 money, @atwhendown datetime, @fifty2wkhi money, @prefix varchar(10), @selldate datetime
declare mycur cursor for
	select s.stockID, s.ticker, min(ns.atwhen), sd.price, sd.volume
	from NOVEMBERSTDDEV2 ns
	inner join stockdata sd on sd.stockID = ns.stockID and sd.atwhen =ns.atwhen 
	inner join stock s on s.stockid = ns.stockID
	group by s.stockID, s.ticker, sd.price, sd.volume
	order by stockID

open mycur
fetch next from mycur into @sid,@tick,@dt, @p,@v
	while @@fetch_Status=0
		begin
		select top 1 @atwhenup = min(atwhen)
		from stockdata where stockID=@sid
		--and atwhen > dateadd(month,2,@dt)
		and atwhen > @dt
		and (price > @p*1.2)
		and price > 0
		group by atwhen
		order by atwhen asc

		select top 1 @atwhendown = min(atwhen)
		from stockdata where stockID=@sid
		--and atwhen > dateadd(month,2,@dt)
		and atwhen > @dt
		and (price < @p*0.95)
		and price > 0
		group by atwhen
		order by atwhen asc
		
		select @fifty2wkhi = max(price)
		from stockdata where stockID=@sid
		and atwhen between dateadd(wk,-52,@dt) and @dt

		if @p between (@fifty2wkhi*0.9) and (@fifty2wkhi * 1.1)
			begin
				set @prefix='*'
			end
		else
			begin
				set @prefix=''
			end

		if @atwhenup < @atwhendown
		begin
			select @price2 = price
			from stockdata where stockID=@sid
			and atwhen = @atwhenup
			and price > 0

			select @selldate = @atwhenup
		end
		else
		begin
			select @price2 = price
			from stockdata where stockID=@sid
			and atwhen = @atwhendown
			and price > 0

			select @selldate = @atwhendown
		end

		if @price2 > @p
			begin
			insert into @linx
			select '<a style=color:green; id=t' + convert(varchar,@sid) + ' onclick="changeActiveStates(this)" target=_chart href="amstock.aspx?ticker=' + @tick + '&bd='+ convert(varchar,@dt,101) + '&bc=winnerbuy">' + @prefix + @tick + ': buy at $' + convert(varchar,@p) + ' on ' + convert(varchar,@dt,101) + ' sell: ' + convert(varchar,@selldate,101) + '</a><br>'
			--select '<a style=color:green; id=t' + convert(varchar,@sid) + ' onclick="changeActiveStates(this)" target=_chart href="http://data.moneycentral.msn.com/scripts/chrtsrv.dll?symbol=US%3a' + @tick + '&E1=0&LPR=2&C1=2&C5=10&C5D=1&C6=2006&C7=3&C7D=1&C8=2008&D5=0&D2=0&D4=1&DD=1&width=800&height=600&DC=1&CE=3&CF=1">' + @tick + ': buy at $' + convert(varchar,@p) + ' on ' + convert(varchar,@dt,101) + ' @' + convert(varchar,@v) + ' volume</a><br>'
			end
		else
			begin
			insert into @linx
			select '<a style=color:red; id=t' + convert(varchar,@sid) + ' onclick="changeActiveStates(this)" target=_chart href="amstock.aspx?ticker=' + @tick + '&bd='+ convert(varchar,@dt,101) + '&bc=loserbuy">'+ @prefix + @tick + ': buy at $' + convert(varchar,@p) + ' on ' + convert(varchar,@dt,101) + ' sell: ' + convert(varchar,@selldate,101) + '</a><br>'
			--select '<a style=color:red; id=t' + convert(varchar,@sid) + ' onclick="changeActiveStates(this)" target=_chart href="http://data.moneycentral.msn.com/scripts/chrtsrv.dll?symbol=US%3a' + @tick + '&E1=0&LPR=2&C1=2&C5=10&C5D=1&C6=2006&C7=3&C7D=1&C8=2008&D5=0&D2=0&D4=1&DD=1&width=800&height=600&DC=1&CE=3&CF=1">' + @tick + ': buy at $' + convert(varchar,@p) + ' on ' + convert(varchar,@dt,101) + ' @' + convert(varchar,@v) + ' volume</a><br>'
			end		

		fetch next from mycur into @sid,@tick,@dt, @p,@v
		end
close mycur
deallocate mycur
set nocount off
select * from @linx

/*
select distinct top 1000 s.stockID, s.ticker, min(ns.atwhen), sd.price, sd.volume, 'http://moneycentral.msn.com/investor/charts/chartdl.aspx?PT=7&compsyms=&D4=1&DD=1&D5=0&DCS=2&MA0=1&MA1=2&CP=1&C5=10&C5D=1&C6=2006&C7=3&C7D=1&C8=2008&C9=-1&CF=1&DC=1&D7=&D6=&showchartbt=Redraw+chart&symbol=US%3A' + s.ticker + '&nocookie=1&SZ=0',

'<a style=color:' + case when min(sd2.price) > sd.price then 'green' else'red' end + '; id=t' + convert(varchar,s.stockID) + ' onclick="changeActiveStates(this)" target=_chart href="http://data.moneycentral.msn.com/scripts/chrtsrv.dll?symbol=US%3a' + s.ticker + '&E1=0&LPR=2&C1=2&C5=10&C5D=1&C6=2006&C7=3&C7D=1&C8=2008&D5=0&D2=0&D4=1&DD=1&width=800&height=600&DC=1&CE=3&CF=1">' + s.ticker + ': buy at $' + convert(varchar,sd.price) + ' on ' + convert(varchar,min(ns.atwhen),101) + ' @' + convert(varchar,sd.volume) + ' volume</a><br>',
min(sd2.price)
--'<a id=t' + convert(varchar,s.stockID) + ' onclick="changeActiveStates(this)" target=_chart href="http://finance.yahoo.com/charts?s=' + s.ticker + '#chart3:symbol=mdrx;range=20070103,20080101;indicator=volume;charttype=line;crosshair=on;ohlcvalues=0;logscale=off;source=undefined">' + s.ticker + ': buy at $' + convert(varchar,sd.price) + ' on ' + convert(varchar,min(ns.atwhen),101) + ' @' + convert(varchar,sd.volume) + ' volume</a><br>'
from NOVEMBERSTDDEV2 ns
inner join stockdata sd on sd.stockID = ns.stockID and sd.atwhen =ns.atwhen 
inner join stock s on s.stockid = ns.stockID
inner join stockdata sd2 on sd2.stockID = s.stockID and sd2.atwhen >=dateadd(month,2,ns.atwhen)
group by s.stockID, s.ticker, sd.price, sd.volume, sd2.price
order by stockID
*/
