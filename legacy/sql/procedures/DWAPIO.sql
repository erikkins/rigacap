-- SqlProcedure: [dbo].[DWAPIO]

SET FMTONLY OFF
set nocount on

declare @curdate datetime, @today datetime
declare @tprice money

select @today = convert(char(4),datepart(year, getdate())) + '-' + right('00' + convert(varchar(2),datepart(month, getdate())),2) + '-'+ right('00' + convert(varchar(2), datepart(day, getdate())),2)

select @curdate = max(atwhen) from stockdata
where stockID=@stockID
select @tprice = price
from StockData
where StockID = @StockID
and AtWhen= @curdate

if @tprice < 10.00
	begin
		return
	end


select @curdate  = @startdate

while @curdate <= @enddate
	begin
		if datepart(dw,@curdate) != 1 and datepart(dw,@curdate) != 7
		begin
			if not exists (select * from DataCache where stockID=@StockID and AtWhen=@curdate and CacheDate=@today)				
				begin
						--Print 'getDWAPriceIO ' + convert(varchar, @stockID) + ' on ' + convert(varchar,@curdate)
						exec getDWAPriceIO @stockID, @curdate
				end
		end
	select @curdate = dateadd(day,1,@curdate)
	end

set nocount off
