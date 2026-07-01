-- SqlProcedure: [dbo].[watchSellUnder200DMAP]

set nocount on

declare @watchID int, @stockID int, @shares decimal(8,3)
declare @buyID int, @lastPrice money, @lastDataDate datetime
declare @lastPrice2 money, @lastPrice3 money
declare @lastDataDate2 datetime
declare @200DMAP money

declare @diff int
declare @today datetime, @buydate datetime
select @today = getdate()

select @watchID = watchID 
from Watch 
where ProcName = 'watchSellUnder200DMAP'

exec addWatchHistory @watchID, @today

if @channel is null
	begin
		declare a2cur cursor for
			select buyID, stockID, shares, atwhen from StockBuy sb where sb.status=0
	end
else
	begin
		declare a2cur cursor for
			select buyID, stockID, shares, atwhen from StockBuy sb where sb.status=0 and sb.channel = @channel
	end
open a2cur
	fetch next from a2cur into @buyID, @stockID, @shares, @buydate
	while @@fetch_status=0
		begin								
			select @diff = datediff(day, @buydate, @today)
			if @diff < 30
				begin
					continue
				end

			select @lastDataDate = LastDataDate
			from Stock
			where stockID=@stockID

			declare @undercount int
			declare @prices table
			(
				theprice money
			)
			insert into @prices
				select top 5 Price		
				from StockData sd
				where sd.StockID = @StockID
				and sd.AtWhen <= @LastDataDate
				order by sd.AtWhen DESC

			

			--get the 200DMAP
			--select @200DMAP = avg(price)
			--from stockdata 
			--where atwhen between dateadd(day,-200,@lastDataDate) and dateadd(day,1,@lastdataDate)
			--and StockID = @StockID

			/*
			select top 200 @200DMAP = avg(price)
			from stockdata
			where atwhen <= @lastDataDate
			and stockID = @StockID
			group by atwhen
			order by atwhen desc
			*/

			select @200DMAP = dbo.fn200DMA(@stockID, @lastDataDate)
			
			select @undercount= count(*)
			from @prices
			where theprice < @200DMAP
			if @undercount = 5
				begin
					--sell!
					exec saveAudit @LastDataDate, 'Below 200DMAP', @stockID, 'BELOW200DMAP'
					exec addSell @buyID, @watchID, @LastDataDate, @shares, 'Below 200DMAP'
				end			

		fetch next from a2cur into @buyID, @stockID, @shares, @buydate
		end
close a2cur
deallocate a2cur
