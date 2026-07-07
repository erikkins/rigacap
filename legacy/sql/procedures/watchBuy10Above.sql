-- SqlProcedure: [dbo].[watchBuy10Above]

--this is a buy watch, but we're not using the startdate ever...

declare @stockID int, @dwapdate datetime

declare @watchID int
declare @ticker varchar(5)

declare @now datetime
select @now = getdate()
declare @audit varchar(8000)

select @watchID = watchID 
from Watch 
where ProcName = 'watchBuy10Above'

declare @newhighdate datetime, @newhighprice money

exec addWatchHistory @watchID, @now


declare hpwb10cur cursor for
	select stockID, atwhen from HoldingPen where code = 'NEWHIGH'
	open hpwb10cur
	fetch next from hpwb10cur into @stockID, @dwapdate
	while @@fetch_status=0
		begin
			--select @newhighdate = convert(char(4),datepart(year, atwhen)) + '-' + right('00' + convert(varchar(2),datepart(month, atwhen)),2) + '-'+ right('00' + convert(varchar(2), datepart(day, atwhen)),2)
			select @newhighdate = convert(varchar,atwhen,101)
			from HoldingPen
			where StockID = @StockID
			and Code = 'NEWHIGH'

			select @newhighprice = Price
			from StockData
			where StockID = @StockID
			and AtWhen = @newhighdate

			declare @buydate datetime
			declare @lastPrice money
			
			select @buydate = lastDataDate,
			@lastprice = lastprice, @ticker=ticker
			from Stock
			where stockID = @stockID

			declare @total float, @avg float
			select @total = sum(volume)
			from StockData
			where StockID = @StockID
			and atwhen between dateadd(day,-180,@buydate) and dateadd(day,1,@buydate)

			select @avg = @total/180

			if @lastprice >= @newhighprice * 1.10
				begin
					if @avg > 250000
						begin
							select @audit = @ticker + ' exceeded 10% above 52 week high at > 250K volume'
							exec saveAudit @now,  @audit, @stockID, '10%ABOVE','I'

							declare @comment varchar(1000)
							select @comment =  'Price exceeded 10% above 52 Week High at > 250K volume'
							exec addbuy @stockID, @watchID, @buydate,@comment, null, 100, @dwapdate
							exec unhold @stockID, 'NEWHIGH'
						end
					else
						begin
							select @audit = @ticker + ' would have been purchased at 10% above, but volume did not exceed 250K'
							exec saveAudit @now,  @audit, @stockID
						end
				end

		fetch next from hpwb10cur into @stockID, @dwapdate
		end

	close hpwb10cur
	deallocate hpwb10cur
