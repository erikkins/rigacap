-- SqlProcedure: [dbo].[watchMechanical]

set nocount on
/*
OK, this now actually just pulls the mechanical watches into the system,
RATHER than buying anything
*/
/*
First, if the values aren't in the cache, get them there!
*/
if exists (select * from Stock where stockID = @StockID and active=0)
	begin
		return
	end

if not exists (select * from DataCache where stockID=@stockID and AtWhen >= @startdate)
	begin
		declare @today datetime
		select @today = getdate()
		
		exec DWAPIO @stockID, @startdate, @today
	end

create table #tprice
(
predate datetime,
postdate datetime,
predwap float,
postprice money,
)
/*
so, beginning with the start date, see if the dwap
has ever crossed with the price
*/
declare @a datetime, @b datetime
declare @dwappre float
declare @pricepost money

declare @now datetime
select @now = getdate()
declare @audit varchar(8000)

declare @ticker varchar(5)
select @ticker = ticker
from stock
where stockid = @stockID

--trying to set the last buydate
declare @lastPotentialBuyDate datetime

declare pcur cursor for
	select atwhen, dwap 
	from datacache 
	where atwhen between @startdate and getdate()
	and stockID = @stockid
	and dwap > price
	order by atwhen

open pcur
fetch next from pcur into @a, @dwappre
	while @@fetch_status=0
		begin
		
		select @pricepost = price
		from datacache
		where stockID = @stockID
		and atwhen = dateadd(Day, 1, @a)

		if @pricepost > @dwappre
			begin
				select @lastPotentialBuyDate = @a

				insert into #tprice
					select @a, dateadd(Day, 1, @a), @dwappre, @pricepost
			end		

		fetch next from pcur into @a, @dwappre
		end
close pcur
deallocate pcur	


declare @buydate datetime
declare @watchID int

select @watchID = watchID 
from Watch 
where ProcName = 'watchMechanical'

exec addWatchHistory @watchID, @now


/*
declare buycur cursor for
	select postdate from #tprice order by postdate

open buycur
fetch next from buycur into @buydate
if @watchID > 0
	begin
		while @@fetch_status = 0
			begin				
				--exec addBuy @stockID, @watchID, @buydate		
				if not exists (select * from StockInteresting where stockID = @stockID)
					begin
						insert StockInteresting (stockID, atwhen)
							values(@StockID, @buydate)
					end
			fetch next from buycur into @buydate
			end
	end

close buycur
deallocate buycur
*/

if @lastPotentialBuyDate is not null
	begin
		if not exists (select * from stockinteresting where stockID = @stockID)
			begin
				insert StockInteresting (stockID, atwhen)
					values(@stockID, @lastPotentialBuyDate)

				update stock
				set LastDwapDate = @lastPotentialBuyDate
				where stockID = @StockID

				insert into StockDWAP (stockID, DWAPDate)
					values (@stockID, @lastPotentialBuyDate)

				select @audit = 'Adding ' + @ticker + ' to DWAP'
				exec saveAudit @now,  @audit, @stockID
			end
		else
			begin
				declare @lastdwap datetime
				select @lastdwap = atwhen
				from StockInteresting
				where stockid=@stockID

				--make sure the dwap history is intact
				if not exists (select * from stockDWAP where stockID=@stockID and dwapdate=@lastdwap)
					begin
						insert into StockDWAP (stockID, DWAPDate)
							values (@stockID, @lastdwap)
					end

				update StockInteresting
				set atwhen=@lastPotentialBuyDate
				where stockID = @stockID

				update stock
				set LastDwapDate = @lastPotentialBuyDate
				where stockID = @StockID

				insert into StockDWAP (stockID, DWAPDate)
					values (@stockID, @lastPotentialBuyDate)
	
			end
	end
drop table #tprice
return
set nocount off
