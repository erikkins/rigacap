-- SqlProcedure: [dbo].[updateStockActuals]
-- header:
-- CREATE proc [dbo].[updateStockActuals]

CREATE proc [dbo].[updateStockActuals]
as
set nocount on
declare @sid int
declare @lastRecord datetime, @lastActual datetime
declare @lastPrice money, @lastVolume float
declare stcur cursor for
	select stockID from stock

open stcur
	fetch next from stcur into @sid
	while @@fetch_status=0
		begin
		select @lastRecord = LastDataDate
		from Stock
		where stockID = @sid

		select top 1 @lastActual = atwhen,
		@lastPrice = Price,
		@lastVolume = Volume
		from stockdata where stockid=@sid	
		order by atwhen desc

		if @lastactual > @lastRecord
			begin
				--update wtf!
				--Print 'Updating stock ' + convert(varchar(10),@sid)
				
				update stock
				set LastPrice = @lastPrice,
				LastVolume = @lastVolume,
				LastDataDate = @lastActual
				where stockID=@sid
				
			end

		fetch next from stcur into @sid
		end
close stcur
deallocate stcur

set nocount off
