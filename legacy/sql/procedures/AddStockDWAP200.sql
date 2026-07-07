-- SqlProcedure: [dbo].[AddStockDWAP200]

set nocount on

if exists (select 1 from StockData where StockID = @StockID and atwhen = @atwhen)
	begin
		update stockdata
		set DWAP200 = @dwap200
		where stockID = @stockID
		and atwhen = @atwhen 
	end
else
	begin
		insert into StockData(StockID, AtWhen, Price, Volume, dwap200)
			values(@stockID, @atwhen, 0.00,0, @dwap200)
	end

set nocount off
