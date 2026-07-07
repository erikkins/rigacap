-- SqlProcedure: [dbo].[testSell20Up7Down]
-- header:
-- CREATE proc [dbo].[testSell20Up7Down]

CREATE proc [dbo].[testSell20Up7Down]
as
set nocount on

declare @transid int
declare @startprice money, @buydate datetime, @selldate datetime
declare @watchID int
declare @selldateUp datetime, @selldateDown datetime
Declare @multBuy float, @multSell float
declare @sellcomment varchar(500)

select @watchID = watchID 
from Watch 
where ProcName = 'watchSell20Up7Down'

declare @stockID int

declare allcur cursor for
	select distinct stockID from stocktransaction

open allcur
fetch next from allcur into @stockID
	while @@fetch_status = 0
		begin
			declare sellcur cursor for
				select sd.price, sd.atwhen, st.TransactionID, st.multiplierBuy, st.multiplierSell from StockData sd
				inner join StockTransaction st on st.StockID = sd.StockID
				inner join Stock s on s.stockID=sd.stockID
				and sd.atwhen = st.AtWhenBuy	
				and WatchIDSell is null
				and sd.StockID = @StockID
				and st.stockID=s.stockID
				and s.active=1
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
						
select @stockID, convert(money,@startprice*@multbuy) PriceToExceed, @buydate
						select @selldateUp = min(atwhen) 
						from datacache
						where stockID = @stockID
						and price >= convert(money,@startprice*@multbuy)
						and atwhen > @buydate
						
						if @selldateUp <= Dateadd(day,35,@buydate)
							begin
									update StockTransaction
									set multiplierBuy = 1.5,
									multiplierSell = 1.1,
									sellcomment = 'Short term run-up (50%/10%)<br>'
									where transactionID = @transid
									Print 'Updating Multiplier for ' + Convert(Varchar,@transid)						

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
										Print 'Sell stock ' + convert(varchar,@stockID) + ' on ' + convert(varchar,@selldate)
										/*
										update StockTransaction
										set WatchIDSell = @WatchID,
										AtWhenSell = @selldate
										where TransactionID = @TransID
										*/
									end
							end

					fetch next from sellcur into @startprice, @buydate, @transid, @multbuy, @multsell
					end
			close sellcur
			deallocate sellcur

		fetch next from allcur into @stockID
		end

close allcur
deallocate allcur

set nocount off
