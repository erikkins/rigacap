-- SqlProcedure: [dbo].[watchSell90DaysBoring]

set nocount on

declare @watchID int, @stockID int, @shares decimal(8,3), @atwhen datetime
declare @buyID int
declare @diff int
declare @today datetime
declare @above int, @below int
declare @buyprice money

select @watchID = watchID 
from Watch 
where ProcName = 'watchSell90DaysBoring'

select @today = getdate()


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
	fetch next from a2cur into @buyID, @stockID, @shares, @atwhen
	while @@fetch_status=0
		begin	

			--see if we've held for 90+ days
			select @diff = datediff(day, @atwhen, @today)

			if @diff >= 90
				begin
					select @buyprice = price
					from stockdata
					where stockID=@stockID
					and atwhen = @atwhen

					--now check if the price has ever gone +- 8% during the holding period
					select @above = count(*) 
					from stockdata sd
					where stockID = @stockID
					and atwhen between @atwhen and @today
					and price > @buyprice * 1.08

					select @below = count(*) 
					from stockdata sd
					where stockID = @stockID
					and atwhen between @atwhen and @today
					and price < @buyprice * .92			

					--if the price never wavered outside of 8% in 90+ days, then sell, it's boring!
					if @above=0 and @below = 0
					begin
						--sell!
						exec saveAudit @today, '90 Days Boring', @stockID, '90DAYSBORING'
						exec addSell @buyID, @watchID, @today, @shares, '90 Days Boring'
					end	
				end		

		fetch next from a2cur into @buyID, @stockID, @shares, @atwhen
		end
close a2cur
deallocate a2cur
