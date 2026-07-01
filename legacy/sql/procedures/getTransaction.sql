-- SqlProcedure: [dbo].[getTransaction]

set nocount on
	select sb.*, s.Ticker, s.CompanyName, s.lastPrice, s.LastVolume, s.Exchange, s.[52WeekHigh],
	sd1.Price BuyPrice, sd1.Volume BuyVolume, sd2.Price SellPrice, sd2.Volume SellVolume
	from StockBuy sb
	inner join Stock s on s.StockID = sb.StockID
	left join StockSell ss on ss.BuyID=sb.BuyID
	inner join StockData sd1 on sd1.stockID = sb.stockID and sd1.AtWhen = sb.AtWhen
	left outer join StockData sd2 on sd2.stockID = sb.stockID and sd2.AtWhen = ss.AtWhen
	where sb.BuyID = @BuyID
set nocount off
