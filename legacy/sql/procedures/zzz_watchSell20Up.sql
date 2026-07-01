-- SqlProcedure: [dbo].[zzz_watchSell20Up]

set nocount on

declare @transid int
declare @startprice money, @buydate datetime, @selldate datetime
declare @watchID int

select @watchID = watchID 
from Watch 
where ProcName = 'watchSell20Up'

declare sellcur cursor for
	select sd.price, sd.atwhen, st.TransactionID from StockData sd
	inner join StockTransaction st on st.StockID = sd.StockID
	and sd.atwhen = st.AtWhenBuy	
	and WatchIDSell is null

open sellcur
fetch next from sellcur into @startprice, @buydate, @transid
	while @@fetch_status =0
		begin
			--now see if any of our transactions should close
			--on a 20% upswing
		
			select @selldate = min(atwhen) 
			from datacache
			where stockID = @stockID
			and price >= @startprice*1.2

			if @selldate > @buydate
				begin					
					update StockTransaction
					set WatchIDSell = @WatchID,
					AtWhenSell = @selldate
					where TransactionID = @TransID
				end

		fetch next from sellcur into @startprice, @buydate, @transid
		end
close sellcur
deallocate sellcur

set nocount off
