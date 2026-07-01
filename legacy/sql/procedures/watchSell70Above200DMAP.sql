-- SqlProcedure: [dbo].[watchSell70Above200DMAP]

set nocount on

declare @watchID int, @stockID int, @shares decimal(8,3)
declare @buyID int, @lastPrice money, @lastDataDate datetime
declare @200DMAP money
declare @buydate datetime, @buyprice money

select @watchID = watchID 
from Watch 
where ProcName = 'watchSell70Above200DMAP'

declare @now datetime
select @now = getdate()
exec addWatchHistory @watchID, @now


if @channel is null
	begin
		declare a2cur cursor for
			select buyID, stockID, shares from StockBuy sb where sb.status=0
	end
else
	begin
		declare a2cur cursor for
			select buyID, stockID, shares from StockBuy sb where sb.status=0 and sb.channel=@channel
	end


open a2cur
	fetch next from a2cur into @buyID, @stockID, @shares
	while @@fetch_status=0
		begin		
			select @lastPrice = LastPrice, 
			@LastDataDate = LastDataDate
			from Stock s
			inner join StockData sd on sd.StockID = s.StockID and sd.AtWhen=s.LastDataDate
			where s.StockID = @StockID

			--get the 200DMAP
			--select @200DMAP = avg(price)
			--from stockdata 
			--where atwhen between dateadd(day,-200,@lastDataDate) and dateadd(day,1,@lastdataDate)
			--and StockID = @StockID
			
			select @200DMAP = dbo.fn200DMA(@stockID, @lastDataDate)


			if @lastprice is null
				begin
					--Print 'No Last Price in 70AboveDWAP for Stock ' + convert(varchar(10),@StockID) + ' on ' + convert(varchar(20),@RunDate)
					return 0
				end

			if @Buydate = getdate()
				begin
					return 0
				end

			select @buydate = atwhen
			from stockBuy
			where buyID=@buyID

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


			if (@lastprice >= @200DMAP * @mult) and @lastprice > @buyprice * 1.05
				begin
					--sell!
					exec saveAudit @LastDataDate, '70% Above 200DMAP', @stockID, '70%ABOVE200DMAP'
					exec addSell @buyID, @watchID, @LastDataDate, @shares, '70% Above 200DMAP'
				end			

		fetch next from a2cur into @buyID, @stockID, @shares
		end
close a2cur
deallocate a2cur
