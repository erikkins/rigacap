-- SqlProcedure: [dbo].[AddStockDWAP]

set nocount on

if exists (select 1 from StockData where StockID = @StockID and atwhen = @atwhen)
	begin
		update stockdata
		set DWAP=@dwap
		where stockID = @stockID
		and atwhen = @atwhen 
	end
else
	begin
		insert into StockData(StockID, AtWhen, Price, Volume, dwap)
			values(@stockID, @atwhen, 0.00,0,@dwap)
	end

set nocount off
