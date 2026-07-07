-- SqlProcedure: [dbo].[watchBuyAboveMaxPricePostLoss]

--look through all stock transactions that sold for a loss and 
--pull all that don't already have a newer buy
--if their last price exceeds the highest price attained during its 
--previous holding period, buy again!



declare @buydate datetime
declare @selldate datetime
declare @msg varchar(500)
declare @lastprice money
declare @alltime money
declare @lastdatadate datetime
declare @now datetime
select @now = getdate()
declare @buycomment varchar(500)
declare @audit varchar(8000)
declare @ticker varchar(10)
declare @watchID int, @stockID int

select @watchID = watchID 
from Watch 
where ProcName = 'watchBuyAboveMaxPricePostLoss'

exec addWatchHistory @watchID, @now

declare maxlosscur cursor for
	select distinct stockID, max(sb.atwhen)AtWhenBuy, max(ss.atwhen) AtWhenSell
	from stockbuy sb 
	inner join stocksell ss on sb.buyid=ss.buyid 
	where sb.status=1 
	--and ss.watchid= (select watchID from Watch where ProcName='watchSell8Down') --made change to pull ALL buys and try to rebuy
	group by stockID

open maxlosscur 
	fetch next from maxlosscur into @stockID, @buydate, @selldate
	while @@fetch_status=0
		begin
			--Determine if we already have an open buy newer than the loss date...if so, bail
			if not exists (select * from stockbuy where stockid=@stockid and status=0 and atwhen > @selldate)
				begin
					select @ticker = ticker, @lastprice = lastprice, @lastDataDate = lastdatadate
					from stock
					where stockID = @stockID

					select @alltime = max(price)
					from stockdata
					where stockid = @stockID
					and atwhen between @buydate and dateadd(day,1,@selldate)

					if @lastprice is not null and @alltime is not null
						begin
							if @lastprice > @alltime
								begin
									--add the new buy!
									select @audit = 'Buying ' + @ticker + ' on a new high after sell'
									exec saveAudit @now,  @audit, @stockID, 'BUYABOVEMAXPRICEPOSTLOSS', 'I'

									declare @strLastPrice varchar(100)
									select @strLastPrice = convert(varchar,@lastprice)
									if @strLastPrice is null
										begin
											select @strLastPrice = '[unknown]'
										end
									declare @strAllTime varchar(100)
									select @strAllTime = convert(varchar,@alltime)
									if @strAllTime is null
										begin
											select @strAllTime = '[unknown]'
										end

										select @buycomment = 'Yesterday''s price of ' + @strLastPrice + ' exceeds the alltime transaction high price of ' + @strAllTime + ' '											
										exec addBuy @stockID, @watchID, @lastdatadate, @buycomment, null, 100, null
								end
						end
				end

		fetch next from maxlosscur into @stockID, @buydate, @selldate
		end
close maxlosscur
deallocate maxlosscur
