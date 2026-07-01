-- SqlProcedure: [dbo].[watchSell25Up]

declare @watchID int, @stockID int
declare @ticker varchar(10)

declare @now datetime
select @now = getdate()
declare @audit varchar(8000)

select @watchID = watchID 
from Watch 
where ProcName = 'watchSell25Up'

exec addWatchHistory @watchID, @now

declare @lastPrice money, @buyprice money
declare @shares decimal(8,2)
declare @buyID int
declare @lastDataDate datetime
declare @multiplierHigh float, @multiplierLow float


if @channel is null
	begin
		declare sellcur cursor for
			select buyID, shares, multiplierLow, multiplierHigh, StockID from StockBuy where status=0
	end
else
	begin
		declare sellcur cursor for
			select buyID, shares, multiplierLow, multiplierHigh, StockID from StockBuy where status=0 and channel = @channel
	end

	open sellcur
	fetch next from sellcur into @buyid, @shares, @multiplierLow, @multiplierHigh, @stockID
	while @@fetch_status=0
	begin
			select @lastPrice = LastPrice, @LastDataDate = LastDataDate, @ticker = ticker
			from stock
			where stockID = @stockID

			--first check if this is a 25% gainer from the buy...if so, sell 100%
			select @buyprice = price, @shares = shares
			from stockdata sd
			inner join stockbuy sb on sb.stockID = sd.stockID
			where sb.status=0
			and sb.stockID = @stockID
			and sb.buyid=@buyid
			and sb.atwhen=sd.atwhen

			if @lastPrice >= @buyprice *1.25
				begin
					--sell off all!
					select @audit = @ticker + ' Price exceeded 125%, selling all'
					exec saveAudit @now,  @audit, @stockID

					exec addSell @buyID, @watchID, @lastDataDate, 100, 'Price exceeded 125% of buy, selling all'
				end

	fetch next from sellcur into @buyid, @shares, @multiplierLow, @multiplierHigh, @stockID
	end
close sellcur
deallocate sellcur
