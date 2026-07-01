-- SqlProcedure: [dbo].[watchSell90DaysBoringRetroDate]

set nocount on

declare @watchID int, @stockID int, @shares decimal(8,3), @atwhen datetime
declare @diff int
declare @today datetime
declare @above int, @below int
declare @buyprice money

select @watchID = watchID 
from Watch 
where ProcName = 'watchSell90DaysBoringRetroDate'


exec addWatchHistory @watchID, @RunDate

select @StockID = stockID,
@shares = shares,
@atwhen = atwhen
from StockBuy 
where BuyID=@BuyID
	

	--see if we've held for 90+ days
	select @diff = datediff(day, @atwhen, @RunDate)

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
			and atwhen between @atwhen and @RunDate
			and price > @buyprice * 1.08

			select @below = count(*) 
			from stockdata sd
			where stockID = @stockID
			and atwhen between @atwhen and @RunDate
			and price < @buyprice * .92			

			--if the price never wavered outside of 8% in 90+ days, then sell, it's boring!
			if @above=0 and @below = 0
			begin
				--sell!
				--make sure the rundate is a weekday, if not move forward until it is
				declare @isWeekday bit
				select @isWeekday = dbo.fn_IsWeekDay(@RunDate)
				if @isWeekday = 1
					begin
						exec saveAudit @RunDate, '90 Days Boring', @stockID, '90DAYSBORING'
						exec addSell @buyID, @watchID, @RunDate, @shares, '90 Days Boring'
						return 1
					end
			end	
		end		

return 0
