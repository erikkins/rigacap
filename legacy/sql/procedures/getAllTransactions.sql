-- SqlProcedure: [dbo].[getAllTransactions]

set nocount on

	if @OnlyOpen = 1
			begin
				select * from StockBuy
				where StockID = @StockID				
				and Status = 0
				order by AtWhen desc
			end
		else
			begin
				select * from StockBuy sb
				left outer join StockSell ss on ss.BuyID = sb.BuyID
				order by sb.AtWhen
			end
set nocount off
