-- SqlProcedure: [dbo].[getDWAPrice]

set nocount on
SET FMTONLY OFF
create table #td
(
dwa float,
rdwa float,
atwhen datetime,
price money,
weight float
)
declare @startdate datetime, @enddate datetime

select @enddate = dateadd(day,1,@dateofinterest)
select @startdate = dateadd(year,-1,@enddate)

declare @firstdate datetime
select @firstdate = min(atwhen) from stockdata
where stockID = @stockID

if @firstdate > @startdate
	select @startdate = @firstdate

declare @atwhen datetime, @price money, @volume float,@sumvol float, @sumrvol float, @tempdwa float, @temprdwa float
declare @tempweight float, @today datetime
select @today = convert(char(4),datepart(year, getdate())) + '-' + right('00' + convert(varchar(2),datepart(month, getdate())),2) + '-'+ right('00' + convert(varchar(2), datepart(day, getdate())),2)

select @sumrvol = null, @temprdwa = null

--this is the total volume for the whole period (for DWAP)
select @sumvol = sum(convert(bigint,volume))
from stockdata
where stockID = @stockid
and atwhen between @startdate and @enddate
and (DatePart(dw,atwhen) != 1 and DatePart(dw,atwhen) != 7)

declare sdcur cursor for
	select sd.atwhen, price, volume 
	from stockdata sd	
	inner join stock s	on s.stockID = sd.stockID
	where s.stockid = @stockID
	--and s.active = 1
	and sd.atwhen between @startdate and @enddate
	and (DatePart(dw,sd.atwhen) != 1 and DatePart(dw,sd.atwhen) != 7)

open sdcur
fetch next from sdcur into @atwhen, @Price, @volume
while @@fetch_status=0
	begin
		--this is the regressive volume based on total volume
		--for one year ago from the current date
		if @sumvol > 0
			begin
				select @tempdwa = (@volume/convert(float,@sumvol))*@price		
				select @tempweight = (@volume/convert(float,@sumvol))
				--print 'Range: ' + Convert(varchar,@atwhen) + ' and ' + Convert(varchar,dateadd(year,-1,@atwhen)) + char(10) + char(9) + 'Volume: ' + convert(varchar,@volume) + char(10) + char(9) + ' Sumvol:' + Convert(varchar,@sumvol) + char(10) + char(9) + 'Price: ' + convert(varchar,@price) + char(10) + char(9) + 'Tempdwa:' + Convert(varchar,@tempdwa)

			insert into #td
				values( @tempdwa,@temprdwa, @atwhen, @price, @tempweight)
			end
	fetch next from sdcur into @atwhen, @Price, @volume
	end
close sdcur
deallocate sdcur

select @price = price
from stockdata
where stockID = @stockid
and atwhen = @dateofinterest

if not exists (select * from DataCache where stockID=@StockID and AtWhen=@dateofinterest)
	begin
		if @price > 0
			begin
				insert into DataCache(StockID, AtWhen, Price, DWAP, RDWAP, CacheDate)
					select @StockID, @dateofinterest, @Price, convert(money,sum(dwa)),convert(money, sum(rdwa)), @today from #td
			end
	end
else
	begin
		if @price > 0
			begin
				declare @finaldwap money, @finalrdwap money
				select @finaldwap = convert(money, sum(dwa)),
				--@finalrdwap = convert(money, sum(rdwa))
				@finalrdwap = null
				from #td

				update DataCache
				set price = @price,
				DWAP = @finaldwap,
				RDWAP = @finalrdwap,
				cachedate = @today 
				where StockID = @StockID
				and DataCache.AtWhen = @AtWhen
			end
	end

--select @dateofinterest dateofinterest, convert(money,sum(dwa)) dwaprice, convert(money, sum(rdwa)) rdwaprice, @price price from #td
select @dateofinterest dateofinterest, convert(money,sum(dwa)) dwaprice, null rdwaprice, @price price from #td
--select * from #td
--select sum(weight) from #td
drop table #td

/*
create table #td
(
dwa float,
rdwa float,
atwhen datetime,
price money,
weight float
)
declare @startdate datetime, @enddate datetime

select @enddate = dateadd(day,1,@dateofinterest)
select @startdate = dateadd(year,-1,@enddate)

declare @firstdate datetime
select @firstdate = min(atwhen) from stockdata
where stockID = @stockID

if @firstdate > @startdate
	select @startdate = @firstdate

declare @atwhen datetime, @price money, @volume float,@sumvol float, @sumrvol float, @tempdwa float, @temprdwa float
declare @tempweight float, @today datetime
select @today = convert(char(4),datepart(year, getdate())) + '-' + right('00' + convert(varchar(2),datepart(month, getdate())),2) + '-'+ right('00' + convert(varchar(2), datepart(day, getdate())),2)

--this is the total volume for the whole period (for DWAP)
select @sumvol = sum(convert(bigint,volume))
from stockdata
where stockID = @stockid
and atwhen between @startdate and @enddate
and (DatePart(dw,atwhen) != 1 and DatePart(dw,atwhen) != 7)

declare sdcur cursor for
	select sd.atwhen, price, volume 
	from stockdata sd	
	inner join stock s	on s.stockID = sd.stockID
	where s.stockid = @stockID
	--and s.active = 1
	and sd.atwhen between @startdate and @enddate
	and (DatePart(dw,sd.atwhen) != 1 and DatePart(dw,sd.atwhen) != 7)

open sdcur
fetch next from sdcur into @atwhen, @Price, @volume
while @@fetch_status=0
	begin
		--this is the regressive volume based on total volume
		--for one year ago from the current date
		select @sumrvol = sum(convert(bigint,volume))
		from stockdata
		where stockID = @stockid
		and atwhen between dateadd(year,-1,@atwhen) and dateadd(day,1,@atwhen)
		and (DatePart(dw,atwhen) != 1 and DatePart(dw,atwhen) != 7)


		--weighted avg volume
		select @temprdwa = (@volume/convert(float,@sumrvol))*@price
		select @tempdwa = (@volume/convert(float,@sumvol))*@price		
		select @tempweight = (@volume/convert(float,@sumvol))
		--print 'Range: ' + Convert(varchar,@atwhen) + ' and ' + Convert(varchar,dateadd(year,-1,@atwhen)) + char(10) + char(9) + 'Volume: ' + convert(varchar,@volume) + char(10) + char(9) + ' Sumvol:' + Convert(varchar,@sumvol) + char(10) + char(9) + 'Price: ' + convert(varchar,@price) + char(10) + char(9) + 'Tempdwa:' + Convert(varchar,@tempdwa)

	insert into #td
		values( @tempdwa,@temprdwa, @atwhen, @price, @tempweight)

	fetch next from sdcur into @atwhen, @Price, @volume
	end
close sdcur
deallocate sdcur

select @price = price
from stockdata
where stockID = @stockid
and atwhen = @dateofinterest

if not exists (select * from DataCache where stockID=@StockID and AtWhen=@dateofinterest)
	begin
		if @price > 0
			begin
				insert into DataCache(StockID, AtWhen, Price, DWAP, RDWAP, CacheDate)
					select @StockID, @dateofinterest, @Price, convert(money,sum(dwa)),convert(money, sum(rdwa)), @today from #td
			end
	end
else
	begin
		if @price > 0
			begin
				declare @finaldwap money, @finalrdwap money
				select @finaldwap = convert(money, sum(dwa)),
				@finalrdwap = convert(money, sum(rdwa))
				from #td

				update DataCache
				set price = @price,
				DWAP = @finaldwap,
				RDWAP = @finalrdwap,
				cachedate = @today 
				where StockID = @StockID
				and DataCache.AtWhen = @AtWhen
			end
	end

select @dateofinterest dateofinterest, convert(money,sum(dwa)) dwaprice, convert(money, sum(rdwa)) rdwaprice, @price price from #td
--select * from #td
--select sum(weight) from #td
drop table #td
*/
set nocount off
