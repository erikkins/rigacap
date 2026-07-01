-- SqlProcedure: [dbo].[watchSell5Down]

set nocount on

declare @watchID int, @stockID int
declare @buyID int, @shares decimal(8,3), @buyPrice money, @multLow float, @lastPrice money, @buydate datetime
declare @selldate datetime

--select @selldate = convert(varchar,getdate(),101)

select @watchID = watchID 
from Watch 
where ProcName = 'watchSell5Down'

declare @now datetime
select @now = getdate()
exec addWatchHistory @watchID, @now

declare eightcur cursor for
	select buyID, shares, price, multiplierLow, sb.stockID, sb.atwhen from StockBuy sb inner join stockData sd on sd.StockID=sb.StockID and sd.AtWhen=sb.AtWhen where sb.status=0

open eightcur
	fetch next from eightcur into @buyID, @shares, @buyPrice, @multLow, @stockID, @buydate
	while @@fetch_status=0
		begin

		select @lastPrice = LastPrice, @selldate = convert(varchar,lastdatadate,101)
		from Stock
		where StockID = @StockID

		if @multLow is null
			begin
				--we're just selling on 5% down
				if @lastprice <= @buyprice * .95
					begin
						exec saveAudit @selldate, 'Stock dropped 5% below buy price', @stockID
						exec addSell @buyID, @watchID, @selldate, @shares, 'Stock dropped 5% below buy price'
					end
			end
		else
			begin
				--we're selling on whatever the down multiplier is
				if @lastprice <= @buyprice * @multLow
					begin
						declare @msg varchar(500)
						declare @val varchar(50)
						select @val = convert(varchar,@buyprice * @multlow)
						if @val = null
							begin
								select @val = ''
							end
						select @msg = 'Stock dropped ' + @val + ' below buy price'
						exec saveAudit @selldate, @msg, @stockID
						exec addSell @buyID, @watchID, @selldate, @shares, 'Stock dropped below buy price'
					end
			end

		fetch next from eightcur into @buyID, @shares, @buyPrice, @multLow, @stockID, @buydate
		end
close eightcur
deallocate eightcur
