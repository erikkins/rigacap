-- SqlProcedure: [dbo].[watchSell8DownRetroDate]

set nocount on

declare @watchID int, @stockID int
declare @shares decimal(8,3), @buyPrice money, @multLow float, @lastPrice money, @buydate datetime
declare @dwapdate datetime
--select @selldate = convert(varchar,getdate(),101)

select @watchID = watchID 
from Watch 
where ProcName = 'watchSell8DownRetroDate'

exec addWatchHistory @watchID, @RunDate

select @StockID = stockID,
@shares = shares,
@BuyDate = atwhen,
@multLow = multiplierLow,
@DwapDate = DwapDate
from StockBuy 
where BuyID=@BuyID

select @buyPrice = Price
from StockData sd
inner join stockBuy sb on sb.StockID=sd.StockID
where sd.Atwhen = @BuyDate
and sd.stockID=@stockID


		select @lastPrice = Price
		from StockData
		where StockID=@StockID
		and atwhen = @RunDate

		if @lastprice is null or @buyprice is null
		begin
			--if @dwapdate is null
			--	begin
			--		Print 'LastPrice is null in 8% down'
			--	end
			return 0
		end

		if @multLow is null
			begin
				--we're just selling on 8% down
				if @lastprice <= @buyprice * .92
					begin

						if @RunDate = @BuyDate
							begin
								Print 'SELL DATE SAME AS BUY DATE'
								Print '     ' + convert(varchar, @lastprice) + ' is 8% below ' + convert(varchar,@buyprice)
							end

						exec saveAudit @RunDate, 'Stock dropped 8% below buy price', @stockID
						exec addSell @buyID, @watchID, @RunDate, @shares, 'Stock dropped 8% below buy price'	
						Print 'Selling 8% Down'-- StockID:' + Convert(varchar, @stockID) + ' , BuyID:' + Convert(varchar,@BuyID) + ' , RunDate:' + Convert(varchar,@RunDate,101)
						return 1					
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
						exec saveAudit @RunDate, @msg, @stockID
						exec addSell @buyID, @watchID, @RunDate, @shares, 'Stock dropped below buy price'
						Print 'Selling 8% Down'-- StockID:' + Convert(varchar, @stockID) + ' , BuyID:' + Convert(varchar,@BuyID) + ' , RunDate:' + Convert(varchar,@RunDate,101)
						return 1
					end
			end

		return 0
