-- SqlProcedure: [dbo].[DWAP]

SET FMTONLY OFF
set nocount on

create table #t
(
Atwhen datetime,
dwap float,
rdwap float,
Price money
)
declare @curdate datetime, @today datetime
select @today = convert(char(4),datepart(year, getdate())) + '-' + right('00' + convert(varchar(2),datepart(month, getdate())),2) + '-'+ right('00' + convert(varchar(2), datepart(day, getdate())),2)
select @curdate  = @startdate
while @curdate <= @enddate
	begin
		if datepart(dw,@curdate) != 1 and datepart(dw,@curdate) != 7
		begin			
			if exists (select * from DataCache where stockID=@StockID and AtWhen=@curdate and CacheDate=@today)
				begin
					insert into #t
						select Atwhen, DWAP, RDWAP, Price from DataCache where StockID = @StockID and atwhen=@curdate
				end
			else
				begin
					insert into #t		
						exec getDWAPrice @stockID, @curdate				
			end			
		end
	select @curdate = dateadd(day,1,@curdate)
	end

select AtWhen, Price, dwap, rdwap from #t
drop table #t

set nocount off
