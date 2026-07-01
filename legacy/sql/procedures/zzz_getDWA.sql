-- SqlProcedure: [dbo].[zzz_getDWA]

set nocount on
SET FMTONLY OFF
create table #t
(
dwa float,
atwhen datetime,
price money,
volume int
)

declare @atwhen datetime, @price money, @volume float, @sumvol float, @tempdwa float
declare sdcur cursor for
	select atwhen, price, volume 
	from stockdata 
	where stockid = @stockID 
	and atwhen between @startdate and dateadd(day,1,@enddate)


open sdcur
fetch next from sdcur into @atwhen, @Price, @volume
while @@fetch_status=0
	begin

	select @sumvol = sum(convert(bigint,volume))
	from stockdata
	where stockID = @stockid
	and atwhen between dateadd(year,-1,@atwhen) and dateadd(day,1,@atwhen)
	
	select @tempdwa = (@volume/convert(float,@sumvol))*@price
	--print 'Range: ' + Convert(varchar,@atwhen) + ' and ' + Convert(varchar,dateadd(year,-1,@atwhen)) + char(10) + char(9) + 'Volume: ' + convert(varchar,@volume) + char(10) + char(9) + ' Sumvol:' + Convert(varchar,@sumvol) + char(10) + char(9) + 'Price: ' + convert(varchar,@price) + char(10) + char(9) + 'Tempdwa:' + Convert(varchar,@tempdwa)

	insert into #t
		values( @tempdwa, @atwhen, @price, @volume)

	fetch next from sdcur into @atwhen, @Price, @volume
	end
close sdcur
deallocate sdcur

select dwa, atwhen, price, volume from #t
drop table #t

set nocount off
