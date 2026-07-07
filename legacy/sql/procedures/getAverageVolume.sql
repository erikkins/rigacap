-- SqlProcedure: [dbo].[getAverageVolume]

set nocount on 

	declare @stockID int
	select @stockID = stockID
	from Stock
	where ticker = @ticker

	declare @today datetime
	select @today = getdate()

	select avg(volume) as AverageVolume
	from StockData
	where StockID=@StockID
	and atwhen between dateadd(year,-1, @today) and @today

set nocount off
