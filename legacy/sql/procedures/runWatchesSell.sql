-- SqlProcedure: [dbo].[runWatchesSell]

set nocount on

declare @buyDate datetime, @StockID int, @DwapDate datetime
declare @now datetime
select @now = getdate()
declare @temp datetime
declare @sellret int
declare @channel char(1)

select @buyDate = AtWhen,
@StockID = stockID,
@DwapDate = DwapDate,
@Channel=channel
from stockBuy
where BuyID=@BuyID

select @temp = @buyDate
select @sellret = 0

while (@temp < @now) and @sellret = 0
	begin
		/*
		if exists (select * from stocksplit where stockID=@stockID and atwhen=@temp and applydate is null)
		begin
			exec applySplit @stockID, @temp
		end	
		*/
	--we need to get out if we've stumbled upon another buy for the same stock
		if exists (select * from stockbuy where stockID=@StockID and atwhen=@temp and buyID != @BuyID and channel=@channel)
			begin
				--delete THIS buy
				Print 'Stumbled upon another buy during the same period'
				delete from stockBuy where buyID=@buyID
				select @sellret=1
				select @temp=@now
				break
			end


	exec @sellret = runWatchesRetroDate @BuyID, @temp

	if @sellret = 1
		begin			
			select @temp = @now
			break
		end

	select @temp = DateAdd(day,1,@temp)
	end

return @sellret

set nocount off

--select * from stockbuy where channel='F' and dwapdate is null
