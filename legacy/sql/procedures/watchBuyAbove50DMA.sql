-- SqlProcedure: [dbo].[watchBuyAbove50DMA]

--this is a buy watch, but we're not using the startdate ever...

declare @buydate datetime, @lastvolume float
declare @watchID int
declare @lastdma real
declare @buycomment varchar(500)
declare @msg varchar(500)
declare @dwapcross money
declare @lastprice money
declare @now datetime
select @now = getdate()
declare @audit varchar(8000)
declare @ticker varchar(5)
/***********************
OK, so 50DMA from the web is PRICE, we want VOLUME
So, we're not going to use the price one anymore, just ignore it
***********************/
exec addWatchHistory @watchID, @startdate

--let's make sure this is an interesting stock
if not exists (select * from StockInteresting where StockID = @stockID)
	begin
		return
	end

select @ticker = ticker
from stock
where stockID = @stockID

--let's make sure the dwap crossing occurred after june 1, 2006

declare @dwapcrossdate datetime
select @dwapcrossdate = atwhen from StockInteresting where stockID = @stockID
/*
if @dwapcrossdate < '6/1/2006'
	begin
		return
	end
*/

select @watchID = watchID 
from Watch 
where ProcName = 'watchBuyAbove50DMA'

--if we already have an open transaction for this stock
--via this watch method, don't do it again!
if exists 
	(
	select * from stocktransaction 
	where stockID = @stockID 
	and watchIDBuy = @watchID
	and watchIDSell is null
	)
	begin
		return
	end


create table #50v
(
volume real
)

insert into #50v
select top 50 volume 
from StockData
where stockid=@stockID
order by atwhen desc

select @lastdma = sum(volume)/50 from #50v

drop table #50v
/*
select @lastvolume = LastVolume, @lastprice = LastPrice
from Stock s
where s.stockid = @stockID
*/
--clean up
/*
delete from StockInteresting
where stockID = @stockID
and atwhen < dateadd(month,-2,getdate())
*/

--if the 50DMAV is < 100,000, then we don't even want this stock
if @lastdma < 100000
	begin
		delete from stockInteresting where stockID = @stockID
		--make sure we're not on any watch lists
		delete from holdingpen where stockID = @stockID
		return
	end


select @buydate = lastdatadate, @lastvolume = lastVolume, @lastprice = lastPrice
from Stock
where stockID = @stockID


if @lastvolume is null OR @lastprice is null
	begin
		return
	end

if @lastprice < 10.00
	begin
		return
	end

--ditch out if it's a distribution day
declare @yesterdaydate datetime, @yesterdayprice money
select @yesterdaydate = max(atwhen)
from StockData
where stockID = @stockID
and atwhen < @buydate

select @yesterdayprice = Price
from StockData
where StockID = @stockID
and atwhen = @yesterdaydate

if @yesterdayprice > @lastprice
	begin
		return
	end
--end distribution ditchout

	
	if @lastdma is not null and @lastvolume is not null
		begin
			if @lastdma > 0 and @lastvolume > 0
				begin
				--see if the last price exceeds the last 50dma
					if @lastvolume > convert(float,@lastdma) * convert(float,2)
						begin
						--select @msg= convert(varchar,@lastvolume) + ' is > ' + convert(varchar,convert(float,@lastdma)*convert(float,1.5))
						--print @msg

						select @dwapcross = price
						from stockdata
						where stockid = @stockID
						and atwhen = @dwapcrossdate

						--our current price is less than the price
						--that it crossed the dwap
						if @lastprice <= @dwapcross
							begin
								return
							end

						--we're pulling the string values early because if they're null
						--we end up getting an empty string!
						declare @strLastVolume varchar(100)
						select @strLastVolume = convert(varchar,convert(bigint,@lastvolume))
						if @strLastVolume is null
							begin
								select @strLastVolume = '[unknown]'
							end

						declare @strLastDMA varchar(100)
						select @strLastDMA = convert(varchar,convert(bigint,@lastdma))
						if @strLastDMA is null
							begin
								select @strLastDMA = '[unknown]'
							end

						select @buycomment = 'Yesterday''s volume of ' + @strLastVolume + ' exceeds 2X the 50DMA volume of ' + @strLastDMA + ' '

						declare @strDWAPWhen varchar(100)
						select @strDWAPWhen = convert(varchar,atwhen,101) from StockInteresting where stockID = @stockID
						if @strDWAPWhen is null
							begin
								select @strDWAPWhen = '[unknown]'
							end

						declare @strDWAPCross varchar(100)
						select @strDWAPCross = convert(varchar,@dwapcross)
						if @strDWAPCross is null
							begin
								select @strDWAPCross = '[unknown]'
							end

		
						select @buycomment = @buycomment + '<br>Price crossed dwap on ' + @strDWAPWhen + ' @ ' + @strDWAPCross + '<br>'

						--if so, update the transaction to a buy and update the buy date
							--exec addBuy @stockID, @watchID, @buydate, @buycomment
							Print 'Adding to holding pen'
							exec hold @stockID, @buydate, 'ABOVE50DMA'

							select @audit = @ticker + ' added to ABOVE50DMA holding pen'
							exec saveAudit @now,  @audit, @stockID, 'ABOVE50DMA','I'

						/*
						now delete the record from StockInteresting
						since it was SO interesting we actually bought it
						...no need to buy it tomorrow too
						*/
							delete from StockInteresting
							where StockID = @StockID
						end
					else
						begin
							select @msg = convert(varchar,@lastvolume) + ' is not > ' + convert(varchar,convert(float,@lastdma)*2)
							print @msg
						end
				end
		end	
return
