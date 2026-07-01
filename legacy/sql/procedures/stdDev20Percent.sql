-- SqlProcedure: [dbo].[stdDev20Percent]

set nocount on

declare @stdev money
select @stdev = dbo.StdDev1Year(@stockID, @atwhen)

--select @stdev

declare @t table
(
price money,
volume float,
vwp float
)

declare @totalvol float, @avgvolume float
select @totalvol = sum(volume), @avgvolume = avg(volume) from stockdata where stockID=@stockID 
and atwhen between dateadd(year,-1, @atwhen) and dateadd(day,1,@atwhen)
--select @totalvol

if @avgvolume < 500000
	return

insert into @t
select price, volume, price * (volume/@totalvol)
from stockdata where stockID = @stockID
and atwhen between dateadd(year,-1, @atwhen) and dateadd(day,1,@atwhen)
group by price, volume
order by price * (volume/@totalvol) desc

--select * from stockdata where stockID = 178 and atwhen between '8/1/2006' and '8/1/2007' and price = 44.75


--select * from @t order by vwp desc

declare @range table
(
price money
)

declare @tempvol float
set @tempvol = 0
declare @p money, @v float
declare countdown cursor for
	select price, volume from @t order by vwp desc
open countdown
fetch next from countdown into @p, @v
	while @@fetch_status = 0 AND @tempvol < (@totalvol * .2)
		begin
			insert into @range
				select @p
			select @tempvol = @tempvol + @v
			fetch next from countdown into @p, @v
		end
close countdown
deallocate countdown

--select min(price) Minimum, max(price) Maximum, avg(price) Average from @range

declare @avg money
select @avg = avg(price) from @range

if @avg < 15
	return

select stockID, atwhen from stockdata
where stockID = @stockID
and atwhen = @atwhen
and price > @avg + 2 * @stdev
and volume > @avgvolume * 3
and price > 15
and volume > 1500000

set nocount off
