-- SqlProcedure: [dbo].[watchSell70Above200DMAPRetroDate]

set nocount on

declare @watchID int, @stockID int, @shares decimal(8,3)
declare @lastPrice money
declare @200DMAP money
declare @buydate datetime
declare @buyprice money
declare @dwapdate datetime
declare @buyIDlink int

select @watchID = watchID 
from Watch 
where ProcName = 'watchSell70Above200DMAPRetroDate'


exec addWatchHistory @watchID, @RunDate

select @StockID = stockID,
@shares = shares,
@BuyDate = atwhen,
@DwapDate = dwapdate,
@BuyIDLink = buyIDLink
from StockBuy 
where BuyID=@BuyID

--Print 'Checking 70 Above 200'
			--get the 200DMAP
			--select @200DMAP = avg(price)
			--from stockdata 
			--where atwhen between dateadd(day,-200,@RunDate) and dateadd(day,1,@RunDate)
			--and StockID = @StockID

			select @200DMAP = dbo.fn200DMA(@stockID, @RunDate)

			select @lastprice = Price
			from StockData
			where StockID=@StockID
			and atwhen = @RunDate	

			if @lastprice is null
				begin
					--Print 'No Last Price in 70AboveDWAP for Stock ' + convert(varchar(10),@StockID) + ' on ' + convert(varchar(20),@RunDate)
					return 0
				end

			--Print 'Threshold = ' + convert(varchar(10),@200DMAP*1.7)
			--Print 'LastPrice = ' + convert(varchar(10),@lastPrice)

			--don't sell on the buy date...ever
			if @rundate = @Buydate
				begin
					return 0
				end

			select @buyprice = price
			from stockData
			where stockID=@StockID
			and Atwhen = @buydate

			declare @mult decimal(2,1)
			select @mult=1.7

			--lower prices are more volatile, so let's make sure it's pushed hard
			if @lastprice < 50
				begin
					select @mult = 1.8
				end

			--rebuy, so make sure we're taking advantage of the heightened excitement
			--if we sold on 70% up, we're probably already up there, so move it up to 100% up
			if @dwapdate is null
				begin
					declare @sellwatchID int
					select @sellwatchID = WatchID 
					from StockSell 
					where BuyID = @BuyIDLink
					if @sellwatchID = @watchID
						begin
							select @mult=2
						end
				end

			--let's lock in a 5% gain atleast
			if (@lastprice >= @200DMAP * @mult) and @lastprice > @buyprice * 1.05
				begin
					--sell!
					exec saveAudit @RunDate, '70% Above 200DMAP', @stockID, '70%ABOVE200DMAP'
					exec addSell @buyID, @watchID, @RunDate, @shares, '70% Above 200DMAP'
					Print 'SOLD at 70% above 200DMAP'
					return 1
				end			

			return 0
