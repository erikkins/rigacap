-- SqlProcedure: [dbo].[watchSell20Up7Down]

set nocount on

declare @transid int
declare @startprice money, @buydate datetime, @selldate datetime
declare @watchID int
declare @selldateUp datetime, @selldateDown datetime
Declare @multBuy float, @multSell float, @multRunUp float, @sellDateRunUp datetime
declare @sellcomment varchar(500)
declare @now datetime
select @now = getdate()
declare @audit varchar(8000)

select @watchID = watchID 
from Watch 
where ProcName = 'watchSell20Up7Down'

exec addWatchHistory @watchID, @now

declare sellcur cursor for
	select sd.price, sd.atwhen, st.TransactionID, st.multiplierBuy, st.multiplierSell from StockData sd
	inner join StockTransaction st on st.StockID = sd.StockID
	inner join Stock s on s.stockID=sd.stockID
	and sd.atwhen = st.AtWhenBuy	
	and WatchIDSell is null
	and sd.StockID = @StockID
	and st.stockID=s.stockID
	--and s.active=1 --don't limit to active, because if we bought it, it must've been active at some point
	--and st.status='B' --only pick the bought transactions

open sellcur
fetch next from sellcur into @startprice, @buydate, @transid, @multbuy, @multsell
	while @@fetch_status =0
		begin
			--now see if any of our transactions should close
			--on a 20% upswing
			select @sellcomment = sellcomment from stocktransaction where transactionID = @transid
			if @sellcomment is null
				begin
					select @sellcomment = ''
				end		

			if @multbuy is null
				begin
					select @multbuy = 1.3
				end
			if @multsell is null
				begin
					select @multsell = .9
				end
			
		
			select @selldateUp = min(atwhen) 
			from datacache
			where stockID = @stockID
			and price >= convert(money,@startprice*@multbuy)
			and atwhen > @buydate

			select @multRunUp = 1.2
			select @selldateRunUp = min(atwhen) 
			from datacache
			where stockID = @stockID
			and price >= convert(money,@startprice*@multRunUp)
			and atwhen > @buydate
			
			if @selldateRunUp <= Dateadd(day,35,@buydate)
				begin
						update StockTransaction
						set multiplierBuy = 4,
						multiplierSell = 1.1,
						sellcomment = 'Short term run-up (400%/10%)<br>'
						where transactionID = @transid
						--Print 'Updating Multiplier for ' + Convert(Varchar,@transid)						
		
						select @multBuy = 1.5, @multsell=1.1

	
						select @audit = 'Multiplier updated for transaction ' + convert(varchar,@transid)
						exec saveAudit @now,  @audit, @stockID

						select @selldateUP = null
				end

			select @selldateDown = min(atwhen) 
			from datacache
			where stockID = @stockID
			and price <= convert(money,@startprice*@multsell)
			and atwhen > @buydate		
			
			if @selldateUp is not null and @selldatedown is null
				begin
					select @selldate = @selldateUp
					--Print 'SelldateUp because selldateDown is null'
				end
			else
				begin
					if @selldateup is null and @selldatedown is not null
						begin	
							select @selldate = @selldatedown
							--Print 'SelldateDown because selldateUp is null'
						end
					else
						begin							
							if @selldateUp < @selldateDown
								begin	
									--we're up 20%, SELL
									select @selldate = @selldateUp
									--Print 'SelldateUp because it is before selldateDown'
								end
							else
								begin
									--we're down 7%, SELL
									select @selldate = @selldateDown
									--Print 'SelldateDown because it is before selldateUp'
									--Print '      SDU:' + convert(varchar,@selldateUp)
									--Print '      SDD:' + convert(varchar,@selldateDown)
								end		
						end
				end

			if @selldate is not null
				begin
					if @selldate > @buydate
						begin					
							update StockTransaction
							set WatchIDSell = @WatchID,
							AtWhenSell = @selldate
							where TransactionID = @TransID


						select @audit = 'Selling transaction ' + convert(varchar,@transid)
						exec saveAudit @now,  @audit, @stockID
						end
				end

		fetch next from sellcur into @startprice, @buydate, @transid, @multbuy, @multsell
		end
close sellcur
deallocate sellcur

set nocount off
