-- SqlProcedure: [dbo].[watchSellLadderProfits]

declare @watchID int, @stockID int
declare @ticker varchar(10)

declare @now datetime
select @now = getdate()
declare @audit varchar(8000)

select @watchID = watchID 
from Watch 
where ProcName = 'watchSellLadderProfits'

exec addWatchHistory @watchID, @now

declare @lastPrice money, @buyprice money
declare @shares decimal(8,2)
declare @buyID int
declare @lastDataDate datetime
declare @multiplierHigh float, @multiplierLow float


--we would need a cursor here!
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
			select @lastPrice = LastPrice, @LastDataDate = convert(varchar,LastDataDate,101), @ticker = ticker
			from stock
			where stockID = @stockID

			--first check if this is a 25% gainer from the buy...if so, sell 50%
			select @buyprice = price, @shares = shares
			from stockdata sd
			inner join stockbuy sb on sb.stockID = sd.stockID
			where sb.status=0
			and sb.stockID = @stockID
			and sb.buyid=@buyid
			and sb.atwhen=sd.atwhen

			if @lastPrice >= @buyprice *1.25 and @multiplierLow is null
				begin
					--sell off half!
					select @audit = @ticker + ' Price exceeded 125%, selling half on ladder profits'
					exec saveAudit @now,  @audit, @stockID

					exec addSell @buyID, @watchID, @lastDataDate, 50, 'Price exceeded 125% of buy, selling half on ladder profits'
				end

			--now see if we need to raise the ladder
			if @lastPrice >= @buyprice * 1.44 and @multiplierLow is null
				begin
					select @audit = @ticker + ' Price exceeded 144% of buy price, moving ladder up'
					exec saveAudit @now,  @audit, @stockID

					update StockBuy
					set multiplierLow = @buyprice * 1.104 --this is 8% below 20% above the buy price
					where buyID = @buyID
				end


	fetch next from sellcur into @buyid, @shares, @multiplierLow, @multiplierHigh, @stockID
	end
close sellcur
deallocate sellcur
